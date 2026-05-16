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
    def __init__(self, config: Settings):
        self.config = config
        
        # Initialize Mistral client
        self.mistral = MistralClient(
            base_url=config.MISTRAL_API_URL,
            model=config.MISTRAL_MODEL,
            timeout=config.LLM_TIMEOUT,
            max_tokens=config.LLM_MAX_TOKENS
        )
        
        # Service URLs
        self.intent_agent_url = config.INTENT_AGENT_URL
        self.schema_agent_url = config.SCHEMA_AGENT_URL
        self.entity_resolution_url = config.ENTITY_RESOLUTION_AGENT_URL
        self.sql_agent_url = config.SQL_AGENT_URL
        self.validation_agent_url = config.VALIDATION_AGENT_URL
        self.execution_agent_url = config.EXECUTION_AGENT_URL
        self.audit_agent_url = config.AUDIT_AGENT_URL

    async def process_query(self, user_query: str, user_role: str) -> dict:
        """
        Process user query through entire pipeline.
        
        Flow:
        1. Call Intent Agent → get intent
        2. Call Schema Agent → get tables
        3. Call Entity Resolution → get joins
        4. Call SQL Agent → generate SQL
        5. Call Validation Agent → verify safety
        6. Call Execution Agent → execute & get results
        7. Call Audit Agent → log access
        8. Return results to user
        """
        
        try:
            logger.info(f"[ORCHESTRATOR] Processing query: {user_query[:50]}...")
            
            # Step 1: Intent Recognition
            logger.info("[ORCHESTRATOR] → Intent Agent")
            intent_response = await self._call_intent_agent(user_query)
            
            if not intent_response["success"]:
                return self._error_response(f"Intent recognition failed: {intent_response.get('error')}")
            
            intent_data = intent_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Intent: {intent_data.get('primary_category', 'unknown')}")
            
            # Step 2: Schema Understanding
            logger.info("[ORCHESTRATOR] → Schema Agent")
            schema_response = await self._call_schema_agent(intent_data)
            
            if not schema_response["success"]:
                return self._error_response(f"Schema mapping failed: {schema_response.get('error')}")
            
            schema_data = schema_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Tables retrieved")
            
            # Step 3: Entity Resolution
            logger.info("[ORCHESTRATOR] → Entity Resolution Agent")
            entity_response = await self._call_entity_resolution(
                intent_data,
                schema_data
            )
            
            if not entity_response["success"]:
                return self._error_response(f"Entity resolution failed: {entity_response.get('error')}")
            
            entity_data = entity_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Join paths determined")
            
            # Step 4: SQL Generation
            logger.info("[ORCHESTRATOR] → SQL Agent")
            sql_response = await self._call_sql_agent(
                intent_data,
                schema_data,
                entity_data
            )
            
            if not sql_response["success"]:
                return self._error_response(f"SQL generation failed: {sql_response.get('error')}")
            
            sql_data = sql_response["data"]
            logger.info(f"[ORCHESTRATOR] ← SQL generated (parameterized)")
            
            # Step 5: Validation
            logger.info("[ORCHESTRATOR] → Validation Agent")
            validation_response = await self._call_validation_agent(sql_data, user_role)
            
            if not validation_response["success"]:
                return self._error_response(f"Validation failed: {validation_response.get('error')}")
            
            validation_data = validation_response["data"]
            
            if not validation_data.get("safe", False):
                logger.error(f"[ORCHESTRATOR] Query failed validation: {validation_data.get('issues', [])}")
                return self._error_response(f"Query unsafe: {validation_data.get('issues', [])}")
            
            logger.info(f"[ORCHESTRATOR] ← Query validated (safe)")
            
            # Step 6: Execution
            logger.info("[ORCHESTRATOR] → Execution Agent")
            execution_response = await self._call_execution_agent(
                sql_data,
                validation_data,
                user_role
            )
            
            if not execution_response["success"]:
                return self._error_response(f"Execution failed: {execution_response.get('error')}")
            
            execution_data = execution_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Results returned")
            
            # Step 7: Audit Logging
            logger.info("[ORCHESTRATOR] → Audit Agent")
            await self._call_audit_agent(
                user_role,
                intent_data,
                schema_data,
                execution_data,
                user_query
            )
            logger.info(f"[ORCHESTRATOR] ← Audit logged")
            
            # Return final results
            return {
                "status": "success",
                "results": execution_data.get("data", []),
                "metadata": execution_data.get("metadata", {}),
                "pipeline": {
                    "intent": intent_data,
                    "schema": schema_data,
                    "entity_resolution": entity_data,
                    "sql": sql_data,
                    "validation": validation_data
                }
            }
        
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error: {str(e)}")
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

    async def _call_sql_agent(self, intent_data: dict, schema_data: dict, entity_data: dict) -> dict:
        """Call SQL Generation Agent."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.sql_agent_url}/generate_sql",
                    json={
                        "intent": intent_data.get("primary_category", "retrieve"),
                        "primary_entity": entity_data.get("primary_entity", "customer"),
                        "tables": schema_data.get("tables", ["customers"]),
                        "join_paths": entity_data.get("join_structure", []),
                        "limit": 100
                    },
                    timeout=10
                )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_validation_agent(self, sql_data: dict, user_role: str) -> dict:
        """Call Validation Agent."""
        try:
            # Flatten parameter values for validation
            params = sql_data.get("parameters", [])
            flat_params = [p.get("value", p) if isinstance(p, dict) else p for p in params]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.validation_agent_url}/validate_query",
                    json={
                        "sql": sql_data.get("sql", ""),
                        "parameters": flat_params,
                        "user_role": user_role
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

    def _error_response(self, error: str) -> dict:
        """Format error response."""
        return {
            "status": "error",
            "error": error,
            "results": [],
            "metadata": {}
        }
