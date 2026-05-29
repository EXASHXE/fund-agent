"""Vector store collection definitions and schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


@dataclass
class CollectionField:
    name: str
    field_type: FieldType
    index: bool = True


@dataclass
class CollectionSchema:
    name: str
    description: str
    vector_size: int = 1536
    fields: list[CollectionField] = field(default_factory=list)


COLLECTIONS: dict[str, CollectionSchema] = {
    "fund_news": CollectionSchema(
        name="fund_news",
        description="News items with embeddings for similarity search",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
            CollectionField("layer", FieldType.INTEGER),
            CollectionField("source", FieldType.STRING),
            CollectionField("relevance_score", FieldType.FLOAT),
        ],
    ),
    "fund_events": CollectionSchema(
        name="fund_events",
        description="Extracted events with embeddings for historical pattern matching",
        vector_size=1536,
        fields=[
            CollectionField("event_type", FieldType.STRING),
            CollectionField("polarity", FieldType.FLOAT),
            CollectionField("magnitude", FieldType.FLOAT),
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
        ],
    ),
    "fund_styles": CollectionSchema(
        name="fund_styles",
        description="Fund style profiles with embeddings for fundalike search",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("style", FieldType.STRING),
            CollectionField("industry", FieldType.STRING),
            CollectionField("size", FieldType.STRING),
        ],
    ),
    "fund_reports": CollectionSchema(
        name="fund_reports",
        description="Historical report chunks with embeddings for pattern matching",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
            CollectionField("score_level", FieldType.STRING),
        ],
    ),
}