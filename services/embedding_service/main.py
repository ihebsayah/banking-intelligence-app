"""
services/embedding_service/main.py
FastAPI entry-point for the Embedding Service (port 8009).
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from embedding_computer import EmbeddingComputer
from schema_embedder import SchemaEmbedder

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Embedding Service",
    description="Compute and serve sentence embeddings; pre-computes schema embeddings on startup",
    version="0.2.0",
)

embedder: EmbeddingComputer = None      # type: ignore
schema_embedder: SchemaEmbedder = None  # type: ignore


# ── Pydantic models ───────────────────────────────────────────────────────────

class EmbeddingRequest(BaseModel):
    text: str

class EmbeddingResponse(BaseModel):
    text: str
    embedding: List[float]

class SimilarityRequest(BaseModel):
    text1: str
    text2: str

class SimilarityResponse(BaseModel):
    similarity: float


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    global embedder, schema_embedder

    embedder = EmbeddingComputer()

    db_url = os.getenv(
        "POSTGRES_EMBEDDINGS_URL",
        "postgresql://embedding_user:securepass123@postgres-embeddings:5432/embeddings",
    )

    schema_embedder = SchemaEmbedder(db_url=db_url, embedder=embedder)

    try:
        await schema_embedder.initialize()
        logger.info("Precomputing schema embeddings…")
        count = await schema_embedder.precompute_all_embeddings()
        logger.info("Schema embeddings precomputed and stored (%d rows).", count)
    except Exception as exc:
        # DB not reachable at dev time — log warning but keep service alive
        logger.warning(
            "Could not store schema embeddings (DB may be unavailable): %s", exc
        )


@app.on_event("shutdown")
async def shutdown() -> None:
    if schema_embedder:
        await schema_embedder.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/embed", response_model=EmbeddingResponse)
async def embed_text(request: EmbeddingRequest) -> EmbeddingResponse:
    """Compute a 384-dim embedding for any text string."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    try:
        vec = embedder.compute_embedding(request.text)
        return EmbeddingResponse(text=request.text, embedding=vec)
    except Exception as exc:
        logger.exception("Embedding failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/similarity", response_model=SimilarityResponse)
async def compute_similarity(request: SimilarityRequest) -> SimilarityResponse:
    """Cosine similarity between two texts."""
    v1 = embedder.compute_embedding(request.text1)
    v2 = embedder.compute_embedding(request.text2)
    return SimilarityResponse(similarity=EmbeddingComputer.similarity(v1, v2))


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "embedding_service"}
