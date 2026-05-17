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

    async def _log(self, agent_name: str, message: str, level: str = "info"):
        if self.log_callback:
            await self.log_callback(agent_name, message, level)

    async def process_query(self, user_query: str, user_role: str) -> dict:
        try:
            logger.info(f"[ORCHESTRATOR] Processing query: {user_query[:50]}...")
            await self._log("orchestrator", f"Processing new query from user '{user_role}'")
            
            # Step 1: Intent Recognition
            logger.info("[ORCHESTRATOR] → Intent Agent")
            await self._log("intent", "Analyzing natural language intent...")
            intent_response = await self._call_intent_agent(user_query)
            
            if not intent_response["success"]:
                err = f"Intent recognition failed: {intent_response.get('error')}"
                await self._log("intent", err, "error")
                return self._error_response(err)
            
            intent_data = intent_response["data"]
            logger.info(f"[ORCHESTRATOR] ← Intent: {intent_data.get('primary_category', 'unknown')}")
            await self._log("intent", f"Identified intent: {intent_data.get('primary_category', 'unknown')}")
            
            # Step 2: Schema Understanding
            logger.info("[ORCHESTRATOR] → Schema Agent")
            await self._log("schema", "Mapping intent to database domains and tables...")
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
            entity_response = await self._call_entity_resolution(
                intent_data,
                schema_data
            )
            
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
            sql_response = await self._call_sql_agent(
                intent_data,
                schema_data,
                entity_data
            )
            
            if not sql_response["success"]:
                err = f"SQL generation failed: {sql_response.get('error')}"
                await self._log("sql", err, "error")
                return self._error_response(err)
            
            sql_data = sql_response["data"]
            logger.info(f"[ORCHESTRATOR] ← SQL generated (parameterized)")
            await self._log("sql", "SQL query successfully generated")
            
            # Step 5: Validation
            logger.info("[ORCHESTRATOR] → Validation Agent")
            await self._log("validation", "Validating query against security policies...")
            validation_response = await self._call_validation_agent(sql_data, user_role)
            
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
            
            # Step 6: Execution
            logger.info("[ORCHESTRATOR] → Execution Agent")
            await self._log("execution", "Executing query against database...")
            execution_response = await self._call_execution_agent(
                sql_data,
                validation_data,
                user_role
            )
            
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
            
            # Step 7: Audit Logging
            logger.info("[ORCHESTRATOR] → Audit Agent")
            await self._log("audit", "Logging query access for compliance...")
            await self._call_audit_agent(
                user_role,
                intent_data,
                schema_data,
                execution_data,
                user_query
            )
            logger.info(f"[ORCHESTRATOR] ← Audit logged")
            await self._log("audit", "Audit log saved successfully.")
            await self._log("orchestrator", "Pipeline complete. Returning results to user.")
            
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
            limit = 100
            order_by = None
            constraints = intent_data.get("explicit_constraints", {})
            threshold = constraints.get("threshold")
            
            if threshold and threshold.startswith("top_"):
                try:
                    limit = int(threshold.split("_")[1])
                    
                    # If we are asking for "top N", we need to order by something.
                    # We can infer a sensible default based on the intent category.
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

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.sql_agent_url}/generate_sql",
                    json={
                        "intent": intent_data.get("primary_category", "retrieve"),
                        "primary_entity": entity_data.get("primary_entity", "customer"),
                        "tables": schema_data.get("tables", ["customers"]),
                        "join_paths": entity_data.get("join_structure", []),
                        "limit": limit,
                        "order_by": order_by
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
