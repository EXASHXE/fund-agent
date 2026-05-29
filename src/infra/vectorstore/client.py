"""Qdrant client wrapper: collection management, initialization."""
from __future__ import annotations

import os

from src.infra.vectorstore.collections import COLLECTIONS, CollectionSchema


def get_qdrant_client():
    """Get or create Qdrant client. Defaults to local mode."""
    from qdrant_client import QdrantClient

    url = os.environ.get("FUND_QDRANT_URL", "")
    path = os.environ.get("FUND_QDRANT_PATH", "data/qdrant_db")

    if url:
        api_key = os.environ.get("FUND_QDRANT_API_KEY", "")
        return QdrantClient(url=url, api_key=api_key)
    else:
        return QdrantClient(path=path)


def init_collections(client=None) -> list[str]:
    """Initialize all required Qdrant collections.

    Args:
        client: Optional QdrantClient instance. Created if not provided.

    Returns:
        List of created collection names.
    """
    if client is None:
        client = get_qdrant_client()

    from qdrant_client.models import Distance, VectorParams

    created = []
    for name, schema in COLLECTIONS.items():
        client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=schema.vector_size,
                distance=Distance.COSINE,
            ),
        )
        # Create payload indexes for filterable fields
        for field in schema.fields:
            if field.index:
                from qdrant_client.models import PayloadSchemaType
                field_type_map = {
                    "string": PayloadSchemaType.KEYWORD,
                    "integer": PayloadSchemaType.INTEGER,
                    "float": PayloadSchemaType.FLOAT,
                }
                payload_type = field_type_map.get(field.field_type.value, PayloadSchemaType.KEYWORD)
                try:
                    client.create_payload_index(
                        collection_name=name,
                        field_name=field.name,
                        field_schema=payload_type,
                    )
                except Exception:
                    pass  # Index may already exist
        created.append(name)

    return created