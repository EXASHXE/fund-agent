"""Embedding pipeline: text → vector via OpenAI-compatible API → Qdrant storage."""
from __future__ import annotations

import os
from typing import Any

from src.vectorstore.collections import COLLECTIONS


_EMBEDDING_API_BASE = os.environ.get("FUND_EMBEDDING_API_BASE", "https://opencode.ai/zen/v1")
_EMBEDDING_API_KEY = os.environ.get("FUND_EMBEDDING_API_KEY", "")
_EMBEDDING_MODEL = os.environ.get("FUND_EMBEDDING_MODEL", "text-embedding-3-small")
_EMBEDDING_DIMENSIONS = int(os.environ.get("FUND_EMBEDDING_DIMENSIONS", "1536"))


def get_embedding_client():
    """Get or create embedding client. Lazy import to avoid startup cost."""
    try:
        from openai import OpenAI
        return OpenAI(
            base_url=_EMBEDDING_API_BASE,
            api_key=_EMBEDDING_API_KEY or "unused",
        )
    except ImportError:
        raise ImportError("openai package required for embeddings: pip install openai")


class EmbeddingPipeline:
    """Embed text → upsert to Qdrant with metadata."""

    def __init__(self, collection: str, qdrant_client=None):
        self.collection_name = collection
        self.schema = COLLECTIONS.get(collection)
        self._client = qdrant_client
        self._embed_client = None

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""
        if self._embed_client is None:
            self._embed_client = get_embedding_client()
        response = self._embed_client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text,
            dimensions=_EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts into vectors."""
        if self._embed_client is None:
            self._embed_client = get_embedding_client()
        response = self._embed_client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=texts,
            dimensions=_EMBEDDING_DIMENSIONS,
        )
        return [item.embedding for item in response.data]

    def embed_and_store(self, items: list[dict], text_field: str = "content") -> list[str]:
        """Embed texts and upsert to Qdrant."""
        if self._client is None:
            raise RuntimeError("Qdrant client not configured. Set FUND_QDRANT_URL.")

        texts = [item[text_field] for item in items]
        vectors = self.embed_batch(texts)

        from qdrant_client.models import PointStruct
        points = []
        for item, vector in zip(items, vectors):
            payload = {k: v for k, v in item.items() if k != text_field}
            points.append(PointStruct(
                id=item.get("id", str(hash(item[text_field]))),
                vector=vector,
                payload=payload,
            ))

        self._client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return [p.id for p in points]

    def search(self, query: str, filters: dict | None = None, limit: int = 10) -> list[dict]:
        """Search for similar items in Qdrant."""
        if self._client is None:
            raise RuntimeError("Qdrant client not configured. Set FUND_QDRANT_URL.")

        query_vector = self.embed(query)

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, dict):
                    continue  # Skip complex filters
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=conditions) if conditions else None

        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
        )
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]