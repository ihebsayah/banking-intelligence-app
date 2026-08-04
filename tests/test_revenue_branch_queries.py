import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/shared")))

from services.orchestrator.orchestrator_agent import OrchestratorAgent


def _mock_client(*post_results):
    """Return (patcher, client) where client.post returns results in sequence."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = post_results
    patcher = patch(
        "services.orchestrator.orchestrator_agent.httpx.AsyncClient"
    )
    mock_client_class = patcher.start()
    mock_client_class.return_value.__aenter__.return_value = mock_client
    return mock_client


def _http_ok(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _revenue_intent(query, threshold="top_10", branch=None):
    intent = {
        "primary_category": "revenue_analysis",
        "explicit_constraints": {"threshold": threshold, "geography": None},
        "filters_structured": [],
    }
    if branch:
        intent["filters_structured"] = [
            {"column": "branches.name", "operator": "=", "value": branch}
        ]
    return intent


@pytest.fixture
def agent():
    config = MagicMock()
    config.SQL_AGENT_URL = "http://sql:8005"
    return OrchestratorAgent(config=config)


@pytest.mark.asyncio
async def test_extract_branch_filter(agent):
    intent = _revenue_intent("q", branch="Sfax Main Branch")
    assert OrchestratorAgent._extract_branch_filter(intent) == {
        "column": "branches.name", "operator": "=", "value": "Sfax Main Branch"
    }
    assert OrchestratorAgent._extract_branch_filter(_revenue_intent("q")) is None


@pytest.mark.asyncio
async def test_revenue_branch_query_assembles_revenue_request(agent):
    client = _mock_client(
        _http_ok({"resolved": True, "branch_id": "BR_TN_001", "name": "Tunis Main Branch", "match_type": "exact"}),
        _http_ok({"sql": "SELECT ...", "parameters": [], "semantic_warnings": []}),
    )
    intent = _revenue_intent("top 10 customers in Tunis Main Branch by revenue", branch="Tunis Main Branch")
    schema_data = {"tables": ["customers", "accounts"]}
    entity_data = {"primary_entity": "customer", "join_structure": []}

    res = await agent._call_sql_agent(intent, schema_data, entity_data, intent and "show me top 10 customers in Tunis Main Branch by revenue")

    assert res["success"] is True
    # First call resolved the branch, second generated SQL
    assert client.post.call_count == 2
    resolve_call = client.post.call_args_list[0]
    assert resolve_call.args[0].endswith("/resolve_branch")
    assert resolve_call.kwargs["json"] == {"name": "Tunis Main Branch"}

    sql_call = client.post.call_args_list[1]
    payload = sql_call.kwargs["json"]
    assert payload["tables"] == ["customers", "accounts", "transactions", "branches"]
    assert payload["filters"] == {"branches.name": "Tunis Main Branch"}
    assert payload["order_by"] == "total_revenue DESC, customers.customer_id ASC"
    assert payload["group_by"] == ["customers.customer_id", "customers.name", "branches.name"]
    assert payload["limit"] == 10
    assert any("FILTER" in c and "frais compte" in c for c in payload["columns"])


@pytest.mark.asyncio
async def test_revenue_global_top10_has_no_branch_filter(agent):
    client = _mock_client(_http_ok({"sql": "SELECT ...", "parameters": []}))
    intent = _revenue_intent("top 10 customers by revenue", branch=None)
    res = await agent._call_sql_agent(intent, {"tables": ["customers"]}, {"primary_entity": "customer", "join_structure": []}, "top 10 customers by revenue")

    assert res["success"] is True
    assert client.post.call_count == 1
    payload = client.post.call_args.kwargs["json"]
    assert payload["order_by"] == "total_revenue DESC, customers.customer_id ASC"
    assert payload.get("filters") in (None, {})


@pytest.mark.asyncio
async def test_unresolvable_branch_fails_closed(agent):
    client = _mock_client(
        _http_ok({"resolved": False, "reason": "not_found", "name": "Sfax Main Branch", "matches": []}),
    )
    intent = _revenue_intent("q", branch="Sfax Main Branch")
    res = await agent._call_sql_agent(intent, {"tables": ["customers"]}, {"primary_entity": "customer", "join_structure": []}, "show me top 10 customers in Sfax Main Branch by revenue")

    assert res["success"] is False
    clarification = res["clarification"]
    assert clarification["requires_clarification"] is True
    assert clarification["clarification_type"] == "branch_resolution"
    assert "not found" in clarification["message"]
    assert clarification["candidates"] == []
    # Only resolve_branch was called — never generated SQL for an unknown branch
    assert client.post.call_count == 1
    assert client.post.call_args.args[0].endswith("/resolve_branch")


@pytest.mark.asyncio
async def test_ambiguous_branch_fails_closed(agent):
    client = _mock_client(
        _http_ok({"resolved": False, "reason": "ambiguous", "name": "Ariana Centre",
                  "matches": [{"branch_id": "BR_002", "name": "Agence Ariana Centre 2"},
                              {"branch_id": "BR_027", "name": "Agence Ariana Centre 27"}]}),
    )
    intent = _revenue_intent("q", branch="Ariana Centre")
    res = await agent._call_sql_agent(intent, {"tables": ["customers"]}, {"primary_entity": "customer", "join_structure": []}, "show me top 10 customers in Ariana Centre by revenue")

    assert res["success"] is False
    clarification = res["clarification"]
    assert clarification["requires_clarification"] is True
    assert "ambiguous" in clarification["message"]
    # candidate names only — no internal branch IDs leaked
    assert clarification["candidates"] == ["Agence Ariana Centre 2", "Agence Ariana Centre 27"]
    assert all("BR_" not in c for c in clarification["candidates"])
    assert client.post.call_count == 1


@pytest.mark.asyncio
async def test_generic_intent_branch_filter_propagated(agent):
    """Part 3: a resolved branch filter must reach the SQL payload for ANY
    intent (not just revenue) with the join path completed, never dropped."""
    client = _mock_client(
        _http_ok({"resolved": True, "branch_id": "BR_TN_001", "name": "Tunis Main Branch", "match_type": "exact"}),
        _http_ok({"sql": "SELECT ...", "parameters": []}),
    )
    intent = {
        "primary_category": "customer_analysis",
        "explicit_constraints": {"threshold": "top_10", "geography": None},
        "filters_structured": [
            {"column": "branches.name", "operator": "=", "value": "Tunis Main Branch"}
        ],
    }
    res = await agent._call_sql_agent(
        intent,
        {"tables": ["customers"]},
        {"primary_entity": "customer", "join_structure": []},
        "show me top 10 customers at Tunis Main Branch",
    )

    assert res["success"] is True
    assert client.post.call_count == 2
    payload = client.post.call_args.kwargs["json"]
    assert payload["filters"] == {"branches.name": "Tunis Main Branch"}
    assert "branches" in payload["tables"]
    assert any("branches" in j.get("to_table") for j in payload["join_paths"])
    # resolved branch context carried downstream (not injected into SQL text)
    assert res["data"]["branch_context"]["name"] == "Tunis Main Branch"


@pytest.mark.asyncio
async def test_generic_intent_unreachable_branch_fails_closed(agent):
    """Part 3/4: when the primary table has no safe path to branches, the
    orchestrator must fail closed instead of silently dropping the constraint."""
    client = _mock_client(
        _http_ok({"resolved": True, "branch_id": "BR_TN_001", "name": "Tunis Main Branch", "match_type": "exact"}),
    )
    intent = {
        "primary_category": "transaction_analysis",
        "explicit_constraints": {"threshold": None, "geography": None},
        "filters_structured": [
            {"column": "branches.name", "operator": "=", "value": "Tunis Main Branch"}
        ],
    }
    res = await agent._call_sql_agent(
        intent,
        {"tables": ["transactions"]},
        {"primary_entity": "transaction", "join_structure": []},
        "transaction activity at Tunis Main Branch",
    )

    assert res["success"] is False
    assert "no safe join path" in res["error"]
    # never generated SQL for an unsatisfiable branch constraint
    assert client.post.call_count == 1
    assert client.post.call_args.args[0].endswith("/resolve_branch")


@pytest.mark.asyncio
async def test_preset_queries_unaffected(agent):
    client = _mock_client(_http_ok({"sql": "SELECT ...", "parameters": []}))
    intent = {"primary_category": "retrieve"}
    res = await agent._call_sql_agent(intent, {"tables": ["customers"]}, {"primary_entity": "customer", "join_structure": []}, "top 10 customers by balance")
    assert res["success"] is True
    payload = client.post.call_args.kwargs["json"]
    assert payload["order_by"] == "accounts.balance DESC"
    assert payload["limit"] == 10
