"""Tests for vector store collection definitions, embedding pipeline, and search."""
import pytest
from unittest.mock import MagicMock, patch
from src.infra.vectorstore.collections import COLLECTIONS, CollectionSchema, CollectionField, FieldType
from src.infra.vectorstore.search import cosine_similarity


class TestCollectionDefinitions:
    def test_all_collections_have_schemas(self):
        assert "fund_news" in COLLECTIONS
        assert "fund_events" in COLLECTIONS
        assert "fund_styles" in COLLECTIONS
        assert "fund_reports" in COLLECTIONS

    def test_collection_schema_fields(self):
        schema = COLLECTIONS["fund_news"]
        assert isinstance(schema, CollectionSchema)
        assert schema.vector_size > 0
        assert len(schema.fields) >= 3
        field_names = [f.name for f in schema.fields]
        assert "fund_code" in field_names
        assert "date" in field_names

    def test_fund_events_collection(self):
        schema = COLLECTIONS["fund_events"]
        field_names = [f.name for f in schema.fields]
        assert "event_type" in field_names
        assert "polarity" in field_names
        assert "magnitude" in field_names


class TestCosineSimilarity:
    def test_orthogonal_vectors(self):
        result = cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        assert result == pytest.approx(0.0)

    def test_identical_vectors(self):
        result = cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        assert result == pytest.approx(1.0)

    def test_opposite_vectors(self):
        result = cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert result == pytest.approx(-1.0)

    def test_zero_vector(self):
        result = cosine_similarity([0.0, 0.0], [1.0, 0.0])
        assert result == 0.0

    def test_arbitrary_vectors(self):
        result = cosine_similarity([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        # (1*4 + 2*5 + 3*6) / (sqrt(14) * sqrt(77)) ≈ 32/32.83 ≈ 0.9746
        assert 0.97 < result < 0.99