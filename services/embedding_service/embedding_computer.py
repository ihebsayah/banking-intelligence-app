"""
services/embedding_service/embedding_computer.py

Wraps sentence-transformers all-MiniLM-L6-v2 (384-dim).
Provides single + batch compute and cosine similarity.
"""
from __future__ import annotations

import logging
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingComputer:
    """Lightweight wrapper around SentenceTransformer."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        logger.info("Loading embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        logger.info("Embedding model loaded (%d-dim)", self.model.get_sentence_embedding_dimension())

    def compute_embedding(self, text: str) -> List[float]:
        """Compute 384-float embedding for a single string."""
        vec = self.model.encode(text, convert_to_numpy=True)
        return vec.tolist()

    def compute_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch encode for efficiency (much faster than one-by-one)."""
        vecs = self.model.encode(texts, convert_to_numpy=True, batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    @staticmethod
    def similarity(vec1: List[float], vec2: List[float]) -> float:
        """Cosine similarity in [0, 1]."""
        v1 = np.array(vec1, dtype=np.float32)
        v2 = np.array(vec2, dtype=np.float32)
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (n1 * n2))
