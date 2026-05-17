import sys
sys.path.insert(0, "/app/shared"); sys.path.insert(0, "/app")

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from mistral_client import MistralClient
from config import Settings
from orchestrator_agent import OrchestratorAgent
import logging

app = FastAPI(title="Orchestrator Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
config = Settings()
mistral_client = None
orchestrator = None

import uuid
from datetime import datetime

active_websockets = set()

async def broadcast_log(agent_name: str, message: str, level: str = "info"):
    log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agentName": agent_name,
        "message": message,
        "level": level
    }
    dead_ws = set()
    for ws in active_websockets:
        try:
            await ws.send_json({"type": "agent_log", "payload": log_entry})
        except:
            dead_ws.add(ws)
    active_websockets.difference_update(dead_ws)

@app.on_event("startup")
async def startup():
    global mistral_client, orchestrator
    logger.info("Initializing Orchestrator Agent with Mistral...")
    
    mistral_client = MistralClient(
        base_url=config.MISTRAL_API_URL,
        model=config.MISTRAL_MODEL,
        timeout=config.LLM_TIMEOUT,
        max_tokens=config.LLM_MAX_TOKENS
    )
    
    is_healthy = await mistral_client.check_health()
    if not is_healthy:
        logger.error("❌ Mistral/Ollama not available!")
        logger.error(f"   Make sure Ollama is running at {config.MISTRAL_API_URL}")
        
    logger.info("✅ Mistral ready")
    
    orchestrator = OrchestratorAgent(config, log_callback=broadcast_log)
    logger.info("✅ Orchestrator Agent initialized")

@app.post("/process_query")
async def process_query(request: dict):
    if not orchestrator:
        return {"status": "error", "error": "Orchestrator not initialized"}
        
    try:
        return await orchestrator.process_query(
            request["query"],
            request.get("user_role", "analyst")
        )
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {"status": "error", "error": str(e)}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator_agent",
        "llm": "mistral",
        "ollama_url": config.MISTRAL_API_URL
    }

@app.websocket("/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.add(websocket)
    try:
        while True:
            await websocket.send_json({
                "type": "health_update",
                "payload": [{"name": "orchestrator", "status": "healthy", "uptime": 0}]
            })
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        active_websockets.discard(websocket)
    except Exception as e:
        active_websockets.discard(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
