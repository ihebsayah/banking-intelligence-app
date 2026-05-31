import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import os
import threading
import requests

DEBUG_SERVICE_URL = os.environ.get("DEBUG_SERVICE_URL", "http://debug-service:8099")
IS_DEBUG_SERVICE = os.environ.get("IS_DEBUG_SERVICE", "false").lower() == "true"

def _send_background_post(url: str, data: dict):
    def post():
        try:
            r = requests.post(url, json=data, timeout=2.0)
            if r.status_code != 200:
                print(f"[DEBUG POST ERROR] {url} returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[DEBUG POST EXCEPTION] {url} failed: {e}")
    threading.Thread(target=post, daemon=True).start()


class AgentPhase(Enum):
    INTENT = "intent_classification"
    SCHEMA = "schema_mapping"
    ENTITY = "entity_resolution"
    SQL = "sql_generation"
    VALIDATION = "validation"
    EXECUTION = "execution"
    AUDIT = "audit_logging"
    INSIGHTS = "insights_generation"
    COMPLIANCE = "compliance_checking"

@dataclass
class AgentLog:
    """Complete log entry for an agent execution"""
    request_id: str
    timestamp: str
    sequence: int
    phase: str
    agent_name: str
    agent_port: int
    input_data: Dict[str, Any]
    processing_time_ms: float
    output_data: Dict[str, Any]
    confidence_score: float
    cache_hit: bool
    error: Optional[str] = None
    error_details: Optional[str] = None
    steps: List[Dict[str, Any]] = None

class DebugLogger:
    """Centralized logging for all agent operations"""
    
    def __init__(self):
        self.logs: Dict[str, List[AgentLog]] = {}  # request_id → list of logs
        self.current_request_id = None
        self.setup_logging()
    
    def setup_logging(self):
        """Configure Python logging"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("BankingIntelligence")
    
    def start_request(self, query: str, user_context: Dict) -> str:
        """Initialize new request logging"""
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        self.current_request_id = request_id
        self.logs[request_id] = []
        
        # Log request start
        self.logger.info(f"NEW REQUEST: {request_id}")
        self.logger.info(f"Query: {query}")
        self.logger.info(f"User: {user_context.get('user_id', 'unknown')}")

        if not IS_DEBUG_SERVICE:
            _send_background_post(
                f"{DEBUG_SERVICE_URL}/debug/request",
                {
                    "request_id": request_id,
                    "query": query,
                    "user_context": user_context
                }
            )
        
        return request_id

    def start_request_direct(self, request_id: str, query: str, user_context: Dict):
        """Directly register request start on debug-service"""
        self.current_request_id = request_id
        self.logs[request_id] = []
        self.logger.info(f"REGISTER REQUEST START: {request_id}")
        self.logger.info(f"Query: {query}")
        self.logger.info(f"User: {user_context.get('user_id', 'unknown')}")

    def log_agent_call(
        self,
        request_id: str,
        phase: AgentPhase,
        agent_name: str,
        agent_port: int,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        processing_time_ms: float,
        confidence_score: float = 1.0,
        cache_hit: bool = False,
        error: Optional[str] = None,
        steps: Optional[List[Dict]] = None
    ) -> AgentLog:
        """Log a single agent execution"""
        phase_val = phase.value if hasattr(phase, 'value') else phase
        log_entry = AgentLog(
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            sequence=len(self.logs.get(request_id, [])) + 1,
            phase=phase_val,
            agent_name=agent_name,
            agent_port=agent_port,
            input_data=input_data,
            processing_time_ms=processing_time_ms,
            output_data=output_data,
            confidence_score=confidence_score,
            cache_hit=cache_hit,
            error=error,
            steps=steps or []
        )
        
        if request_id not in self.logs:
            self.logs[request_id] = []
        
        self.logs[request_id].append(log_entry)
        
        # Print to console for immediate visibility
        self._print_agent_log(log_entry)

        if not IS_DEBUG_SERVICE:
            _send_background_post(
                f"{DEBUG_SERVICE_URL}/debug/log",
                {
                    "request_id": request_id,
                    "phase": phase_val,
                    "agent_name": agent_name,
                    "agent_port": agent_port,
                    "input_data": input_data,
                    "output_data": output_data,
                    "processing_time_ms": processing_time_ms,
                    "confidence_score": confidence_score,
                    "cache_hit": cache_hit,
                    "error": error,
                    "steps": steps or []
                }
            )
        
        return log_entry

    def log_agent_call_direct(self, payload: Any) -> AgentLog:
        """Directly log agent call on debug-service"""
        log_entry = AgentLog(
            request_id=payload.request_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            sequence=len(self.logs.get(payload.request_id, [])) + 1,
            phase=payload.phase,
            agent_name=payload.agent_name,
            agent_port=payload.agent_port,
            input_data=payload.input_data,
            processing_time_ms=payload.processing_time_ms,
            output_data=payload.output_data,
            confidence_score=payload.confidence_score,
            cache_hit=payload.cache_hit,
            error=payload.error,
            steps=payload.steps or []
        )
        
        if payload.request_id not in self.logs:
            self.logs[payload.request_id] = []
            
        self.logs[payload.request_id].append(log_entry)
        self._print_agent_log(log_entry)
        return log_entry
    
    def _print_agent_log(self, log: AgentLog):
        """Pretty-print agent execution to console"""
        status = "✓" if not log.error else "✗"
        cache_indicator = "[CACHE HIT]" if log.cache_hit else ""
        
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║ {status} AGENT: {log.agent_name:<40}║
╚═══════════════════════════════════════════════════════════╝
  Phase:      {log.phase}
  Sequence:   {log.sequence}
  Duration:   {log.processing_time_ms:.2f}ms
  Confidence: {log.confidence_score:.2%} {cache_indicator}
  
  INPUT:
  {json.dumps(log.input_data, indent=2)[:200]}...
  
  OUTPUT:
  {json.dumps(log.output_data, indent=2)[:200]}...
  
  {'ERROR: ' + log.error if log.error else '✓ SUCCESS'}
╚═══════════════════════════════════════════════════════════╝
""")
    
    def get_request_log(self, request_id: str) -> List[AgentLog]:
        """Retrieve all logs for a request"""
        return self.logs.get(request_id, [])
    
    def get_agent_statistics(self, request_id: str) -> Dict:
        """Analyze agent performance for a request"""
        logs = self.get_request_log(request_id)
        
        if not logs:
            return {
                "request_id": request_id,
                "total_agents": 0,
                "total_time_ms": 0,
                "agent_breakdown": [],
                "error_count": 0,
                "cache_hits": 0
            }
        
        total_time = sum(log.processing_time_ms for log in logs)
        
        return {
            "request_id": request_id,
            "total_agents": len(logs),
            "total_time_ms": total_time,
            "agent_breakdown": [
                {
                    "agent": log.agent_name,
                    "time_ms": log.processing_time_ms,
                    "percentage": (log.processing_time_ms / total_time * 100) if total_time > 0 else 0,
                    "confidence": log.confidence_score
                }
                for log in logs
            ],
            "error_count": sum(1 for log in logs if log.error),
            "cache_hits": sum(1 for log in logs if log.cache_hit)
        }

# Global instance
debug_logger = DebugLogger()
