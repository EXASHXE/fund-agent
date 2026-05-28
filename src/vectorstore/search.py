"""Search utilities: cosine similarity, fundalike search."""
from __future__ import annotations

import math


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar_funds(
    fund_code: str,
    limit: int = 5,
    qdrant_client=None,
    embedding_pipeline=None,
) -> list[dict]:
    """Find funds with similar style/exposure profile.

    Args:
        fund_code: Source fund code.
        limit: Number of similar funds to return.
        qdrant_client: Optional QdrantClient instance.
        embedding_pipeline: Optional EmbeddingPipeline for fund_styles collection.

    Returns:
        List of similar funds with similarity scores.
    """
    if embedding_pipeline is None:
        from src.vectorstore.embedding import EmbeddingPipeline
        embedding_pipeline = EmbeddingPipeline(
            collection="fund_styles",
            qdrant_client=qdrant_client,
        )

    return embedding_pipeline.search(
        query=f"fund style profile for {fund_code}",
        limit=limit,
    )