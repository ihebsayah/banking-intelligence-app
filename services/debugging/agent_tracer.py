import asyncio
import time
from functools import wraps
from typing import Callable, Any
from dataclasses import asdict
from .logger import debug_logger, AgentPhase
from .event_emitter import event_emitter

class AgentTracer:
    """Intercepts and traces all agent API calls"""
    
    @staticmethod
    def trace_agent_call(
        phase: AgentPhase,
        agent_name: str,
        agent_port: int
    ):
        """Decorator to trace agent calls"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                # Extract request_id and input_data
                # Support positional arguments if they are passed that way
                request_id = kwargs.get('request_id')
                input_data = kwargs.get('input_data', {})
                
                # Fallback: if not in kwargs, look at args
                if not request_id and len(args) > 0:
                    # Let's inspect first arg if it's a string starting with req-
                    if isinstance(args[0], str) and args[0].startswith('req-'):
                        request_id = args[0]
                if not input_data and len(args) > 1:
                    input_data = args[1]
                
                # If still no request_id, generate or use active current one
                if not request_id:
                    request_id = debug_logger.current_request_id or "req-unknown"
                
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    processing_time = (time.time() - start_time) * 1000
                    
                    # Inspect result data or format appropriately
                    data = result
                    confidence = 1.0
                    cache_hit = False
                    
                    if isinstance(result, dict):
                        # Some endpoints return {"success": True, "data": ...}
                        # We grab "data" if present, otherwise the result itself
                        data = result.get('data', result)
                        confidence = result.get('confidence', 1.0)
                        cache_hit = result.get('cache_hit', False)
                    
                    log_entry = debug_logger.log_agent_call(
                        request_id=request_id,
                        phase=phase,
                        agent_name=agent_name,
                        agent_port=agent_port,
                        input_data=input_data,
                        output_data=data,
                        processing_time_ms=processing_time,
                        confidence_score=confidence,
                        cache_hit=cache_hit,
                        error=None
                    )
                    
                    # Emit websocket event async
                    try:
                        await event_emitter.emit("agent_executed", asdict(log_entry))
                    except Exception as ee_err:
                        print(f"Error emitting trace: {ee_err}")
                        
                    return result
                
                except Exception as e:
                    processing_time = (time.time() - start_time) * 1000
                    
                    log_entry = debug_logger.log_agent_call(
                        request_id=request_id,
                        phase=phase,
                        agent_name=agent_name,
                        agent_port=agent_port,
                        input_data=input_data,
                        output_data={},
                        processing_time_ms=processing_time,
                        confidence_score=0.0,
                        cache_hit=False,
                        error=str(e),
                        error_details=str(e.__traceback__) if hasattr(e, '__traceback__') else None
                    )
                    
                    try:
                        await event_emitter.emit("agent_executed", asdict(log_entry))
                    except Exception as ee_err:
                        print(f"Error emitting trace error: {ee_err}")
                        
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                request_id = kwargs.get('request_id')
                input_data = kwargs.get('input_data', {})
                
                if not request_id and len(args) > 0:
                    if isinstance(args[0], str) and args[0].startswith('req-'):
                        request_id = args[0]
                if not input_data and len(args) > 1:
                    input_data = args[1]
                    
                if not request_id:
                    request_id = debug_logger.current_request_id or "req-unknown"
                
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    processing_time = (time.time() - start_time) * 1000
                    
                    data = result
                    confidence = 1.0
                    cache_hit = False
                    
                    if isinstance(result, dict):
                        data = result.get('data', result)
                        confidence = result.get('confidence', 1.0)
                        cache_hit = result.get('cache_hit', False)
                    
                    log_entry = debug_logger.log_agent_call(
                        request_id=request_id,
                        phase=phase,
                        agent_name=agent_name,
                        agent_port=agent_port,
                        input_data=input_data,
                        output_data=data,
                        processing_time_ms=processing_time,
                        confidence_score=confidence,
                        cache_hit=cache_hit,
                        error=None
                    )
                    
                    # Emit websocket event in sync (schedule in loop if active)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(event_emitter.emit("agent_executed", asdict(log_entry)))
                    except Exception:
                        pass
                    
                    return result
                
                except Exception as e:
                    processing_time = (time.time() - start_time) * 1000
                    
                    log_entry = debug_logger.log_agent_call(
                        request_id=request_id,
                        phase=phase,
                        agent_name=agent_name,
                        agent_port=agent_port,
                        input_data=input_data,
                        output_data={},
                        processing_time_ms=processing_time,
                        confidence_score=0.0,
                        cache_hit=False,
                        error=str(e)
                    )
                    
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(event_emitter.emit("agent_executed", asdict(log_entry)))
                    except Exception:
                        pass
                    
                    raise
            
            # Return appropriate wrapper
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator

# Convenience functions for tracing
def trace_intent_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.INTENT, "Intent Agent", 8002)(func)

def trace_schema_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.SCHEMA, "Schema Agent", 8003)(func)

def trace_entity_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.ENTITY, "Entity Resolution Agent", 8004)(func)

def trace_sql_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.SQL, "SQL Agent", 8005)(func)

def trace_validation_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.VALIDATION, "Validation Agent", 8006)(func)

def trace_execution_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.EXECUTION, "Execution Agent", 8007)(func)

def trace_audit_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.AUDIT, "Audit Agent", 8008)(func)

def trace_insights_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.INSIGHTS, "Insights Agent", 8010)(func)

def trace_compliance_agent(func):
    return AgentTracer.trace_agent_call(AgentPhase.COMPLIANCE, "Compliance Agent", 8011)(func)
