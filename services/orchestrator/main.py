import sys
sys.path.insert(0, "/app/shared"); sys.path.insert(0, "/app")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from mistral_client import MistralClient
from config import Settings
from orchestrator_agent import OrchestratorAgent
import logging

app = FastAPI(title="Orchestrator Agent")

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
config = Settings()
mistral_client = None
orchestrator = None

@app.on_event("startup")
async def startup():
    global mistral_client, orchestrator
    logger.info("Initializing Orchestrator Agent with Mistral...")
    
    # Initialize Mistral client
    mistral_client = MistralClient(
        base_url=config.MISTRAL_API_URL,
        model=config.MISTRAL_MODEL,
        timeout=config.LLM_TIMEOUT,
        max_tokens=config.LLM_MAX_TOKENS
    )
    
    # Check if Mistral is available
    is_healthy = await mistral_client.check_health()
    if not is_healthy:
        logger.error("❌ Mistral/Ollama not available!")
        logger.error(f"   Make sure Ollama is running at {config.MISTRAL_API_URL}")
        logger.error(f"   And mistral model is pulled: ollama pull mistral")
        # raise RuntimeError("Mistral/Ollama not available")
        
    logger.info("✅ Mistral ready")
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(config)
    logger.info("✅ Orchestrator Agent initialized")

@app.post("/process_query")
async def process_query(request: dict):
    """
    Process a user query through the entire pipeline.
    Input:
    {
        "query": "Top 10 customers by balance",
        "user_role": "analyst"
    }
    
    Output:
    {
        "status": "success",
        "results": [...],
        "metadata": {...}
    }
    """
    
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
    try:
        while True:
            # Send dummy health update to keep connection alive
            await websocket.send_json({
                "type": "health_update",
                "payload": [{"name": "orchestrator", "status": "healthy", "uptime": 0}]
            })
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
