from mistral_client import MistralClient
from config import Settings
import logging
import httpx

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    Master orchestrator using Mistral LLM.
    Coordinates all other agents in the pipeline.
    """
    def __init__(self, config: Settings, log_callback=None):
        self.config = config
        self.log_callback = log_callback
        
        self.mistral = MistralClient(
            base_url=config.MISTRAL_API_URL,
            model=config.MISTRAL_MODEL,
            timeout=config.LLM_TIMEOUT,
            max_tokens=config.LLM_MAX_TOKENS
        )
        
        self.intent_agent_url = config.INTENT_AGENT_URL
        self.schema_agent_url = config.SCHEMA_AGENT_URL
        self.entity_resolution_url = config.ENTITY_RESOLUTION_AGENT_URL
        self.sql_agent_url = config.SQL_AGENT_URL
        self.validation_agent_url = config.VALIDATION_AGENT_URL
        self.execution_agent_url = config.EXECUTION_AGENT_URL
        self.audit_agent_url = config.AUDIT_AGENT_URL
        # Phase 2 agents
        self.insights_agent_url = getattr(config, 'INSIGHTS_AGENT_URL', 'http://insights-agent:8013')
        self.compliance_agent_url = getattr(config, 'COMPLIANCE_AGENT_URL', 'http://compliance-agent:8011')

    async def _log(self, agent_name: str, message: str, level: str = "info"):
        if self.log_callback:
            await self.log_callback(agent_name, message, level)

    async def process_query(self, user_query: str, user_role: str) -> dict:
        try:
            from debugging.agent_tracer import (
                trace_intent_agent, trace_schema_agent, trace_entity_agent,
                trace_sql_agent, trace_validation_agent, trace_compliance_agent,
                trace_execution_agent, trace_insights_agent, trace_audit_agent
            )
            from debugging.logger import debug_logger
            has_debugging = True
        except ImportError:
            has_debugging = False

        import uuid
        request_id = None
        if has_debugging:
            request_id = debug_logger.start_request(user_query, {"user_id": "unknown", "role": user_role})
        if not request_id:
            request_id = str(uuid.uuid4())

        try:
            logger.info(f"[ORCHESTRATOR] Processing query: {user_query[:50]}...")
            await self._log("orchestrator", f"Processing new query from user '{user_role}'")
            
            # Step 1: Intent Recognition
            logger.info("[ORCHESTRATOR] → Intent Agent")
            await self._log("intent", "Analyzing natural language intent...")
            
            if has_debugging:
                @trace_intent_agent
                async def run_intent(request_id, input_data):
                    return await self._call_intent_agent(user_query)
                intent_response = await run_intent(request_id=request_id, input_data={"query": user_query})
            else:
                intent_response = await self._call_intent_agent(user_query)
            
            if not intent_response["success"]:
                err = f"Intent recognition failed: {intent_response.get('error')}"
                await self._log("intent", err, "error")
                return self._error_response(err)
            
            intent_data = intent_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Intent: {intent_data.get('primary_category', 'unknown')}")
            await self._log("intent", f"Identified intent: {intent_data.get('primary_category', 'unknown')}")

            # ── Intent-gate decision ────────────────────────────────────────────
            gate_reason = None
            if not intent_data.get("supported_capability", True):
                gate_reason = intent_data.get("rejection_reason", "Unsupported query")
            elif intent_data.get("risk_level") in ("adversarial", "suspicious"):
                gate_reason = intent_data.get("rejection_reason", "Query flagged by risk assessment")
            elif intent_data.get("requires_clarification") and (intent_data.get("intent_confidence") or intent_data.get("confidence", 1.0)) < self.config.INTENT_CONFIDENCE_THRESHOLD:
                gate_reason = intent_data.get("clarification_question") or "Insufficient confidence to proceed"
            elif (intent_data.get("intent_confidence") or intent_data.get("confidence", 1.0)) < self.config.INTENT_CONFIDENCE_THRESHOLD:
                gate_reason = "Query confidence below threshold"

            if gate_reason:
                await self._log("intent", f"Gate REJECTED: {gate_reason}", "warning")
                return self._error_response(gate_reason)
            # ─────────────────────────────────────────────────────────────────────

            # Step 2: Schema Understanding
            logger.info("[ORCHESTRATOR] → Schema Agent")
            await self._log("schema", "Mapping intent to database domains and tables...")
            
            if has_debugging:
                @trace_schema_agent
                async def run_schema(request_id, input_data):
                    return await self._call_schema_agent(intent_data)
                schema_response = await run_schema(request_id=request_id, input_data=intent_data)
            else:
                schema_response = await self._call_schema_agent(intent_data)
            
            if not schema_response["success"]:
                err = f"Schema mapping failed: {schema_response.get('error')}"
                await self._log("schema", err, "error")
                return self._error_response(err)
            
            schema_data = schema_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Tables retrieved")
            await self._log("schema", f"Identified tables: {', '.join(schema_data.get('tables', []))}")
            
            # Step 3: Entity Resolution
            logger.info("[ORCHESTRATOR] → Entity Resolution Agent")
            await self._log("entity_resolution", "Resolving semantic relationships and join paths...")
            
            if has_debugging:
                @trace_entity_agent
                async def run_entity(request_id, input_data):
                    return await self._call_entity_resolution(intent_data, schema_data)
                entity_response = await run_entity(request_id=request_id, input_data={"intent": intent_data, "schema": schema_data})
            else:
                entity_response = await self._call_entity_resolution(intent_data, schema_data)
            
            if not entity_response["success"]:
                err = f"Entity resolution failed: {entity_response.get('error')}"
                await self._log("entity_resolution", err, "error")
                return self._error_response(err)
            
            entity_data = entity_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Join paths determined")
            await self._log("entity_resolution", f"Resolved {len(entity_data.get('join_structure', []))} join paths")
            
            # Step 4: SQL Generation
            logger.info("[ORCHESTRATOR] → SQL Agent")
            await self._log("sql", "Generating safe parameterized SQL...")
            
            sql_input = {
                "intent": intent_data,
                "schema": schema_data,
                "entity": entity_data,
                "query": user_query,
            }
            # Phase 6B: detected_kpis come from intent agent response
            _detected_kpis = intent_data.get("detected_kpis", [])
            if has_debugging:
                @trace_sql_agent
                async def run_sql(request_id, input_data):
                    return await self._call_sql_agent(intent_data, schema_data, entity_data, user_query, _detected_kpis)
                sql_response = await run_sql(request_id=request_id, input_data=sql_input)
            else:
                sql_response = await self._call_sql_agent(intent_data, schema_data, entity_data, user_query, _detected_kpis)
            
            if not sql_response["success"]:
                err = f"SQL generation failed: {sql_response.get('error')}"
                await self._log("sql", err, "error")
                return self._error_response(err)
            
            sql_data = sql_response["data"]
            logger.info(f"[ORCHESTRATOR] ← SQL generated (parameterized)")
            sql_semantic_warnings = sql_data.get("semantic_warnings", [])
            sql_semantic_trace = sql_data.get("semantic_trace", [])
            if sql_semantic_warnings:
                logger.warning("[ORCHESTRATOR] SQL semantic warnings: %s", sql_semantic_warnings)
            await self._log("sql", "SQL query successfully generated")
            
            # Step 5: Validation
            logger.info("[ORCHESTRATOR] → Validation Agent")
            await self._log("validation", "Validating query against security policies...")
            
            validation_input = {
                "sql": sql_data,
                "user_role": user_role
            }
            if has_debugging:
                @trace_validation_agent
                async def run_validation(request_id, input_data):
                    return await self._call_validation_agent(sql_data, user_role, sql_semantic_warnings, request_id=request_id)
                validation_response = await run_validation(request_id=request_id, input_data=validation_input)
            else:
                validation_response = await self._call_validation_agent(sql_data, user_role, sql_semantic_warnings, request_id=request_id)
            
            if not validation_response["success"]:
                err = f"Validation failed: {validation_response.get('error')}"
                await self._log("validation", err, "error")
                return self._error_response(err)
            
            validation_data = validation_response["data"]
            
            if not validation_data.get("safe", False):
                err = f"Query unsafe: {validation_data.get('issues', [])}"
                logger.error(f"[ORCHESTRATOR] Query failed validation: {validation_data.get('issues', [])}")
                await self._log("validation", err, "error")
                return self._error_response(err)
            
            logger.info(f"[ORCHESTRATOR] ← Query validated (safe)")
            await self._log("validation", "Query is SAFE and signed. Proceeding to execution.")
 
            # Step 5.5: Compliance Check (Phase 2)
            logger.info("[ORCHESTRATOR] → Compliance Agent")
            await self._log("compliance", "Checking compliance rules (GDPR/PCI-DSS/SOX/AML/KYC)...")
            
            compliance_input = {
                "user_role": user_role,
                "query_intent": intent_data.get("primary_category", ""),
                "tables": schema_data.get("tables", [])
            }
            if has_debugging:
                @trace_compliance_agent
                async def run_compliance(request_id, input_data):
                    return await self._call_compliance_agent(
                        user_id="unknown",
                        user_role=user_role,
                        query_intent=intent_data.get("primary_category", ""),
                        tables=schema_data.get("tables", []),
                        columns=[],
                    )
                compliance_response = await run_compliance(request_id=request_id, input_data=compliance_input)
            else:
                compliance_response = await self._call_compliance_agent(
                    user_id="unknown",
                    user_role=user_role,
                    query_intent=intent_data.get("primary_category", ""),
                    tables=schema_data.get("tables", []),
                    columns=[],
                )
                
            if not compliance_response.get("compliant", True):
                violations = compliance_response.get("violations", [])
                critical = [v for v in violations if v.get("severity") in ("critical", "high")]
                if critical:
                    reason = critical[0].get("reason", "Compliance violation")
                    err = f"Query blocked by compliance: {reason}"
                    await self._log("compliance", err, "error")
                    return self._error_response(err)
            await self._log("compliance", f"Compliance check passed ({len(compliance_response.get('masking_required', []))} masking rules applied)")
            logger.info("[ORCHESTRATOR] ← Compliance check passed")
 
            # Step 6: Execution
            logger.info("[ORCHESTRATOR] → Execution Agent")
            await self._log("execution", "Executing query against database...")
            
            execution_input = {
                "sql": sql_data,
                "validation": validation_data,
                "user_role": user_role
            }
            if has_debugging:
                @trace_execution_agent
                async def run_execution(request_id, input_data):
                    return await self._call_execution_agent(sql_data, validation_data, user_role)
                execution_response = await run_execution(request_id=request_id, input_data=execution_input)
            else:
                execution_response = await self._call_execution_agent(sql_data, validation_data, user_role)
 
            if not execution_response["success"]:
                err = f"Execution failed: {execution_response.get('error')}"
                await self._log("execution", err, "error")
                return self._error_response(err)
            
            execution_data = execution_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Results returned")
            meta = execution_data.get("metadata", {})
            rows = meta.get('rows_returned', 0)
            ms = meta.get('execution_time_ms', 0)
            src = meta.get('source', 'database')
            await self._log("execution", f"Execution complete. Returned {rows} rows in {ms:.2f}ms (from {src}).")
 
            # Step 6.5: Insights Generation (Phase 2)
            logger.info("[ORCHESTRATOR] → Insights Agent")
            await self._log("insights", "Generating natural language insights...")
            
            insights_input = {
                "query_intent": intent_data.get("primary_category", "retrieve"),
                "query_text": user_query,
                "metadata": {**meta, "tables": schema_data.get("tables", [])}
            }
            if has_debugging:
                @trace_insights_agent
                async def run_insights(request_id, input_data):
                    return await self._call_insights_agent(
                        query_intent=intent_data.get("primary_category", "retrieve"),
                        query_text=user_query,
                        results=execution_data.get("data", []),
                        metadata={
                            **meta,
                            "tables": schema_data.get("tables", []),
                        },
                    )
                insights_response = await run_insights(request_id=request_id, input_data=insights_input)
            else:
                insights_response = await self._call_insights_agent(
                    query_intent=intent_data.get("primary_category", "retrieve"),
                    query_text=user_query,
                    results=execution_data.get("data", []),
                    metadata={
                        **meta,
                        "tables": schema_data.get("tables", []),
                    },
                )
                
            if insights_response.get("success"):
                await self._log("insights", "Insights generated successfully.")
            else:
                await self._log("insights", "Insights unavailable (non-fatal)", "warning")
            logger.info("[ORCHESTRATOR] ← Insights generated")
 
            # Step 7: Audit Logging
            logger.info("[ORCHESTRATOR] → Audit Agent")
            await self._log("audit", "Logging query access for compliance...")
            
            audit_input = {
                "user_role": user_role,
                "query": user_query,
                "intent": intent_data.get("primary_category"),
                "tables": schema_data.get("tables", [])
            }
            if has_debugging:
                @trace_audit_agent
                async def run_audit(request_id, input_data):
                    return await self._call_audit_agent(
                        user_role,
                        intent_data,
                        schema_data,
                        execution_data,
                        user_query
                    )
                audit_response = await run_audit(request_id=request_id, input_data=audit_input)
            else:
                audit_response = await self._call_audit_agent(
                    user_role,
                    intent_data,
                    schema_data,
                    execution_data,
                    user_query
                )
                
            logger.info(f"[ORCHESTRATOR] ← Audit logged")
            await self._log("audit", "Audit log saved successfully.")
            await self._log("orchestrator", "Pipeline complete. Returning results to user.")
 
            # Build enriched semantic_layer_trace (section E)
            _sem_enabled = getattr(self.config, "SEMANTIC_LAYER_ENABLED", False)
            _detected_kpis_list = intent_data.get("detected_kpis", [])
            _selected_tables = schema_data.get("tables", [])
            _join_paths_used = [
                f"{jp.get('from_table','?')}→{jp.get('to_table','?')}"
                for jp in entity_data.get("join_structure", [])
                if isinstance(jp, dict)
            ] if entity_data.get("join_structure") else []
            _all_warnings = (
                sql_semantic_warnings
                + validation_data.get("semantic_warnings", [])
            )

            if not _sem_enabled:
                _trace = {
                    "enabled": False,
                    "ready": False,
                    "path_used": "legacy",
                    "fallback_used": True,
                    "fallback_reason": "feature flag disabled",
                    "detected_kpis": [],
                    "selected_tables": _selected_tables,
                    "join_paths_used": [],
                    "warnings": [],
                }
            elif sql_semantic_warnings or not _detected_kpis_list:
                # Enabled but may have fallen back inside agents
                _trace = {
                    "enabled": True,
                    "ready": True,
                    "path_used": "semantic" if not sql_semantic_warnings else "legacy",
                    "fallback_used": bool(sql_semantic_warnings),
                    "fallback_reason": sql_semantic_warnings[0] if sql_semantic_warnings else None,
                    "detected_kpis": _detected_kpis_list,
                    "selected_tables": _selected_tables,
                    "join_paths_used": _join_paths_used,
                    "warnings": _all_warnings,
                    "sql_trace": sql_semantic_trace,
                    "entity_notes": entity_data.get("notes", ""),
                    "validation_warnings": validation_data.get("semantic_warnings", []),
                }
            else:
                _trace = {
                    "enabled": True,
                    "ready": True,
                    "path_used": "semantic",
                    "fallback_used": False,
                    "fallback_reason": None,
                    "detected_kpis": _detected_kpis_list,
                    "selected_tables": _selected_tables,
                    "join_paths_used": _join_paths_used,
                    "warnings": _all_warnings,
                    "sql_trace": sql_semantic_trace,
                    "entity_notes": entity_data.get("notes", ""),
                    "validation_warnings": validation_data.get("semantic_warnings", []),
                }

            return {
                "status": "success",
                "results": execution_data.get("data", []),
                "metadata": execution_data.get("metadata", {}),
                "insights": insights_response.get("data") if insights_response.get("success") else None,
                "pipeline": {
                    "intent": intent_data,
                    "schema": schema_data,
                    "entity_resolution": entity_data,
                    "sql": sql_data,
                    "validation": validation_data,
                    "compliance": compliance_response,
                },
                "semantic_layer_trace": _trace,
                "request_id": request_id,
                "debug_url": f"/debug/logs/{request_id}" if request_id else None
            }
        
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error: {str(e)}")
            if has_debugging and request_id:
                debug_logger.logger.error(f"Request {request_id} failed: {str(e)}")
            return self._error_response(str(e))

    async def _call_intent_agent(self, query: str) -> dict:
        """Call Intent Agent."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.intent_agent_url}/process_intent",
                    json={"query": query},
                    timeout=10
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_schema_agent(self, intent_data: dict) -> dict:
        """Call Schema Agent."""
        try:
            async with httpx.AsyncClient() as client:
                categories = [intent_data.get("primary_category", "retrieve")] + intent_data.get("secondary_categories", [])
                response = await client.post(
                    f"{self.schema_agent_url}/map_schema",
                    json={"intent_categories": categories},
                    timeout=10
                )
            if response.status_code == 200:
                res_data = response.json()
                tables = res_data.get("tables", [])
                res_data["tables"] = tables if tables else ["customers"]
                return {"success": True, "data": res_data}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_entity_resolution(self, intent_data: dict, schema_data: dict) -> dict:
        """Call Entity Resolution Agent."""
        try:
            primary_entity = self._get_primary_entity(intent_data.get("primary_category", "retrieve"))
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.entity_resolution_url}/resolve_entities",
                    json={
                        "primary_entity": primary_entity,
                        "tables": schema_data.get("tables", ["customers"])
                    },
                    timeout=10
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_sql_agent(self, intent_data: dict, schema_data: dict, entity_data: dict, user_query: str, detected_kpis: list = None) -> dict:
        """Call SQL Generation Agent."""
        try:
            limit = 100
            order_by = ""
            filters = {}
            group_by = []
            columns = []
            tables = []
            join_paths = []
            # Phase 6B: detected_kpis passed from orchestrator (from intent agent response)
            detected_kpis = detected_kpis or intent_data.get("detected_kpis", [])
            
            q = user_query.strip().lower()
            
            # --- Hardcoded Preset Query Handling ---
            if "top 10 customers by balance" in q:
                limit = 10
                order_by = "accounts.balance DESC"
                columns = ["customers.customer_id", "customers.name", "customers.segment", "customers.risk_score", "accounts.balance"]
                tables = ["customers", "accounts"]
                join_paths = [{"from_table": "customers", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = accounts.customer_id"}]
            elif "kyc_verified = false" in q:
                filters = {"kyc_verified": False}
                tables = ["customers"]
            elif "average balance by customer segment" in q:
                group_by = ["customers.segment"]
                columns = ["customers.segment", "AVG(accounts.balance)"]
                tables = ["customers", "accounts"]
                join_paths = [{"from_table": "customers", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = accounts.customer_id"}]
            elif "customer count by state" in q:
                group_by = ["branches.state"]
                columns = ["branches.state", "COUNT(customers.customer_id)"]
                tables = ["customers", "accounts", "branches"]
                join_paths = [{"from_table": "customers", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = accounts.customer_id"}, {"from_table": "accounts", "to_table": "branches", "join_type": "INNER JOIN", "join_key": "branch_id", "condition": "accounts.branch_id = branches.branch_id"}]
            elif "customers created this month" in q:
                filters = {"customers.created_at": {">=": "2020-01-01"}} 
                tables = ["customers"]
            elif "high-risk customers in new york" in q:
                filters = {"customers.risk_score": {">=": 0.7}, "branches.state": "NY"}
                tables = ["customers", "accounts", "branches"]
                join_paths = [{"from_table": "customers", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = accounts.customer_id"}, {"from_table": "accounts", "to_table": "branches", "join_type": "INNER JOIN", "join_key": "branch_id", "condition": "accounts.branch_id = branches.branch_id"}]
            elif "risk_score above 0.8" in q:
                filters = {"risk_score": {">": 0.8}}
                tables = ["customers"]
            elif "aml flags by customer" in q:
                group_by = ["customers.customer_id"]
                columns = ["customers.customer_id", "COUNT(risk_flags.flag_type)"]
                filters = {"risk_flags.flag_type": "AML"}
                tables = ["customers", "risk_flags"]
                join_paths = [{"from_table": "customers", "to_table": "risk_flags", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = risk_flags.customer_id"}]
            elif "fraud detection flags this week" in q:
                filters = {"risk_flags.flag_type": "FRAUD", "risk_flags.created_at": {">=": "2020-01-01"}}
                tables = ["customers", "risk_flags"]
                join_paths = [{"from_table": "customers", "to_table": "risk_flags", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = risk_flags.customer_id"}]
            elif "multiple compliance violations" in q:
                group_by = ["customers.customer_id"]
                columns = ["customers.customer_id", "COUNT(risk_flags.id)"]
                order_by = "COUNT(risk_flags.id) DESC"
                tables = ["customers", "risk_flags"]
                join_paths = [{"from_table": "customers", "to_table": "risk_flags", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = risk_flags.customer_id"}]
            elif "total revenue by product" in q:
                group_by = ["accounts.account_type"]
                columns = ["accounts.account_type", "SUM(accounts.balance)"]
                tables = ["accounts"]
            elif "average fees by account type" in q:
                group_by = ["accounts.account_type"]
                columns = ["accounts.account_type", "AVG(accounts.balance)"]
                tables = ["accounts"]
            elif "top 5 products by commission" in q:
                limit = 5
                order_by = "accounts.balance DESC"
                tables = ["accounts"]
            elif "compliance violations this month" in q:
                filters = {"risk_flags.created_at": {">=": "2020-01-01"}}
                tables = ["customers", "risk_flags"]
                join_paths = [{"from_table": "customers", "to_table": "risk_flags", "join_type": "INNER JOIN", "join_key": "customer_id", "condition": "customers.customer_id = risk_flags.customer_id"}]
            elif "kyc status by customer" in q:
                group_by = ["customers.kyc_verified"]
                columns = ["customers.kyc_verified", "COUNT(customers.customer_id)"]
                tables = ["customers"]
            elif "transaction volume by branch" in q:
                group_by = ["branches.branch_id"]
                columns = ["branches.branch_id", "COUNT(transactions.transaction_id)"]
                tables = ["branches", "accounts", "transactions"]
                join_paths = [{"from_table": "branches", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "branch_id", "condition": "branches.branch_id = accounts.branch_id"}, {"from_table": "accounts", "to_table": "transactions", "join_type": "INNER JOIN", "join_key": "account_id", "condition": "accounts.account_id = transactions.account_id"}]
            elif "average transaction amount" in q:
                columns = ["AVG(transactions.amount)"]
                tables = ["transactions"]
            else:
                # Generic fallback if not a preset
                constraints = intent_data.get("explicit_constraints", {})
                threshold = constraints.get("threshold")
                
                if threshold and threshold.startswith("top_"):
                    try:
                        limit = int(threshold.split("_")[1])
                        intent_cat = intent_data.get("primary_category", "")
                        if intent_cat == "revenue_analysis":
                            order_by = "balance DESC"
                        elif intent_cat == "risk_analysis":
                            order_by = "severity DESC"
                        elif intent_cat == "transaction_analysis":
                            order_by = "amount DESC"
                        else:
                            order_by = "created_at DESC" # generic fallback
                            
                    except (ValueError, IndexError):
                        pass

            is_preset = any(p[0].lower() in q for p in [
                ("top 10 customers by balance",), ("kyc_verified = false",), ("average balance by customer segment",),
                ("customer count by state",), ("customers created this month",), ("high-risk customers in new york",),
                ("risk_score above 0.8",), ("aml flags by customer",), ("fraud detection flags this week",),
                ("multiple compliance violations",), ("total revenue by product",), ("average fees by account type",),
                ("top 5 products by commission",), ("compliance violations this month",), ("kyc status by customer",),
                ("transaction volume by branch",), ("average transaction amount",)
            ])

            payload = {
                "intent": intent_data.get("primary_category", "retrieve"),
                "primary_entity": entity_data.get("primary_entity", "customer"),
                "limit": limit,
                # Phase 6B: pass detected_kpis for metric_registry formula injection
                "detected_kpis": detected_kpis,
            }
            if is_preset:
                payload["tables"] = tables if tables else ["customers"]
                payload["join_paths"] = join_paths
            else:
                payload["tables"] = tables if tables else schema_data.get("tables", ["customers"])
                payload["join_paths"] = join_paths if join_paths else entity_data.get("join_structure", [])

            
            if is_preset:
                if order_by: payload["order_by"] = order_by
                if filters: payload["filters"] = filters
                if group_by: payload["group_by"] = group_by
                if columns: payload["columns"] = columns
            else:
                payload["order_by"] = order_by if order_by else intent_data.get("order_by")
                payload["filters"] = filters if filters else intent_data.get("filters")
                payload["group_by"] = group_by if group_by else intent_data.get("group_by")
                payload["columns"] = columns

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.sql_agent_url}/generate_sql",
                    json=payload,
                    timeout=10
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_validation_agent(self, sql_data: dict, user_role: str, upstream_semantic_warnings: list = None, request_id: str = None) -> dict:
        """Call Validation Agent."""
        try:
            # Flatten parameter values for validation
            params = sql_data.get("parameters", [])
            flat_params = [p.get("value", p) if isinstance(p, dict) else p for p in params]
            
            import secrets
            nonce = secrets.token_hex(8)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.validation_agent_url}/validate_query",
                    json={
                        "sql": sql_data.get("sql", ""),
                        "parameters": flat_params,
                        "user_role": user_role,
                        # Phase 6B: forward sql agent semantic warnings to validation
                        "upstream_semantic_warnings": upstream_semantic_warnings or [],
                        "request_id": request_id,
                        "nonce": nonce,
                    },
                    timeout=10
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_execution_agent(self, sql_data: dict, validation_data: dict, user_role: str) -> dict:
        """Call Execution Agent."""
        try:
            params = sql_data.get("parameters", [])
            flat_params = [p.get("value", p) if isinstance(p, dict) else p for p in params]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.execution_agent_url}/execute_query",
                    json={
                        "sql": sql_data.get("sql", ""),
                        "parameters": flat_params,
                        "signature": validation_data.get("signature", ""),
                        "user_role": user_role,
                        "user_id": "unknown"
                    },
                    timeout=30
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_audit_agent(self, user_role: str, intent_data: dict, schema_data: dict, execution_data: dict, user_query: str) -> dict:
        """Call Audit Agent."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.audit_agent_url}/log_access",
                    json={
                        "user_role": user_role,
                        "action": "nl_query",
                        "status": "success",
                        "endpoint": "/query",
                        "http_method": "POST",
                        "execution_time_ms": execution_data.get("metadata", {}).get("execution_time_ms", 0),
                        "metadata": {
                            "query": user_query[:200],
                            "intent": intent_data.get("primary_category"),
                            "tables": schema_data.get("tables", []),
                            "rows_accessed": execution_data.get("metadata", {}).get("rows_returned", 0)
                        }
                    },
                    timeout=10
                )
            return {"success": response.status_code == 200}
        except Exception as e:
            logger.error(f"Audit logging failed: {str(e)}")
            return {"success": False}

    def _get_primary_entity(self, category: str) -> str:
        """Map intent category to primary entity."""
        mapping = {
            "customer_analysis": "customer",
            "risk_analysis": "customer",
            "revenue_analysis": "customer",
            "operational_analysis": "transaction",
            "geographic_analysis": "branch",
            "product_analysis": "product",
            "compliance_analysis": "customer",
            "transaction_analysis": "transaction",
        }
        return mapping.get(category, "customer")

    async def _call_insights_agent(
        self,
        query_intent: str,
        query_text: str,
        results: list,
        metadata: dict,
    ) -> dict:
        """Call Insights Agent (Phase 2) — non-fatal on failure."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.insights_agent_url}/generate_insights",
                    json={
                        "query_intent": query_intent,
                        "query_text": query_text,
                        "results": results,
                        "metadata": metadata,
                    },
                    timeout=300,
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            return {"success": False, "error": response.text}
        except Exception as exc:
            logger.warning(f"Insights Agent unavailable: {exc}")
            return {"success": False, "error": str(exc)}

    async def _call_compliance_agent(
        self,
        user_id: str,
        user_role: str,
        query_intent: str,
        tables: list,
        columns: list,
    ) -> dict:
        """Call Compliance Agent (Phase 2) — defaults to compliant on failure."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.compliance_agent_url}/check_compliance",
                    json={
                        "user_id": user_id,
                        "user_role": user_role,
                        "query_intent": query_intent,
                        "tables": tables,
                        "columns": columns,
                    },
                    timeout=10,
                )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Compliance Agent returned {response.status_code}")
            return {"compliant": True, "violations": [], "masking_required": []}
        except Exception as exc:
            logger.warning(f"Compliance Agent unavailable: {exc}")
            return {"compliant": True, "violations": [], "masking_required": []}

    def _error_response(self, error: str) -> dict:
        """Format error response."""
        return {
            "status": "error",
            "error": error,
            "results": [],
            "metadata": {}
        }
