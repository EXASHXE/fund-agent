"""DEPRECATED — use src.infra.vectorstore instead."""
import warnings
warnings.warn(
    "src.vectorstore is deprecated, use src.infra.vectorstore instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore.collections import COLLECTIONS, CollectionSchema, CollectionField, FieldType
from src.infra.vectorstore.embedding import EmbeddingPipeline
from src.infra.vectorstore.client import get_qdrant_client, init_collections
from src.infra.vectorstore.search import cosine_similarity, find_similar_funds

__all__ = [
    "COLLECTIONS", "CollectionSchema", "CollectionField", "FieldType",
    "EmbeddingPipeline",
    "get_qdrant_client", "init_collections",
    "cosine_similarity", "find_similar_funds",
]
