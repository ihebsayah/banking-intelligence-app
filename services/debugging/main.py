from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from typing import List, Optional, Dict, Any
from dataclasses import asdict
from pydantic import BaseModel
from logger import debug_logger
from event_emitter import event_emitter

app = FastAPI(title="Debugging Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for incoming REST logs
class RequestStartPayload(BaseModel):
    request_id: str
    query: str
    user_context: Dict[str, Any]

class AgentLogPayload(BaseModel):
    request_id: str
    phase: str
    agent_name: str
    agent_port: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    processing_time_ms: float
    confidence_score: float = 1.0
    cache_hit: bool = False
    error: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None

# ============= REST ENDPOINTS =============

@app.get("/health")
@app.get("/debug/health")
async def health():
    """Health check — both /health (docker) and /debug/health (nginx proxy)"""
    return {"status": "healthy", "service": "debugging"}

@app.post("/debug/request")
async def receive_request_start(payload: RequestStartPayload):
    """Receive and register a request start event from an agent"""
    debug_logger.start_request_direct(
        request_id=payload.request_id,
        query=payload.query,
        user_context=payload.user_context
    )
    return {"status": "ok"}

@app.post("/debug/log")
async def receive_agent_log(payload: AgentLogPayload):
    """Receive and register a single agent log event, and broadcast to websocket clients"""
    log_entry = debug_logger.log_agent_call_direct(payload)
    
    # Broadcast to local event emitter for websocket streaming
    try:
        await event_emitter.emit("agent_executed", asdict(log_entry))
    except Exception as e:
        print(f"Error emitting agent log: {e}")
        
    return {"status": "ok"}

@app.get("/debug/logs/{request_id}")
async def get_request_logs(request_id: str):
    """Get all logs for a request"""
    logs = debug_logger.get_request_log(request_id)
    return {
        "request_id": request_id,
        "log_count": len(logs),
        "logs": [
            {
                "sequence": log.sequence,
                "phase": log.phase,
                "agent_name": log.agent_name,
                "duration_ms": log.processing_time_ms,
                "confidence": log.confidence_score,
                "cache_hit": log.cache_hit,
                "error": log.error,
                "input": log.input_data,
                "output": log.output_data
            }
            for log in logs
        ]
    }

@app.get("/debug/statistics/{request_id}")
async def get_statistics(request_id: str):
    """Get performance statistics for a request"""
    return debug_logger.get_agent_statistics(request_id)

@app.get("/debug/agents")
async def get_all_agents():
    """Get list of all agents"""
    return {
        "agents": [
            {"name": "Intent Agent", "port": 8002, "phase": "intent_classification"},
            {"name": "Schema Agent", "port": 8003, "phase": "schema_mapping"},
            {"name": "Entity Resolution Agent", "port": 8004, "phase": "entity_resolution"},
            {"name": "SQL Agent", "port": 8005, "phase": "sql_generation"},
            {"name": "Validation Agent", "port": 8006, "phase": "validation"},
            {"name": "Execution Agent", "port": 8007, "phase": "execution"},
            {"name": "Audit Agent", "port": 8008, "phase": "audit_logging"},
            {"name": "Insights Agent", "port": 8010, "phase": "insights_generation"},
            {"name": "Compliance Agent", "port": 8011, "phase": "compliance_checking"}
        ]
    }

# ============= WEBSOCKET STREAMING =============

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Broadcast error: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/")
async def websocket_root(websocket: WebSocket):
    """Root WS catch-all — close cleanly instead of 403-ing probes."""
    await websocket.accept()
    await websocket.close(code=1008, reason="Connect to /debug/stream")

@app.websocket("/debug/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time log streaming"""
    await manager.connect(websocket)
    
    async def on_agent_executed(data):
        await manager.broadcast({
            "type": "agent_executed",
            "data": data
        })
    
    # Subscribe to events
    event_emitter.subscribe("agent_executed", on_agent_executed)
    
    try:
        while True:
            # Keep connection alive and listen for client messages
            await websocket.receive_text()
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        event_emitter.unsubscribe("agent_executed", on_agent_executed)
    except Exception as e:
        print(f"WS Exception: {e}")
        manager.disconnect(websocket)
        event_emitter.unsubscribe("agent_executed", on_agent_executed)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099)
