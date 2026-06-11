"""Tests for KnowledgeGraph query enum safety, builder/cache consistency, and event relations."""
from __future__ import annotations

import os
import tempfile

import pytest

from src.graph.builder import KnowledgeGraphBuilder
from src.graph.cache import save_kg_cache, load_kg_cache, kg_cache_key
from src.graph.enrichment import enrich_with_events
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.queries import get_entity_chain, query_exposure, expand_theme, find_related_events
from src.graph.schema import KGEdgeType, EventNode


@pytest.fixture
def sample_fund_data():
    return {
        "code": "110011",
        "name": "Test Fund",
        "fund_type": "equity",
        "holdings": [
            {"stock_code": "600519", "stock_name": "Kweichow Moutai", "weight": 9.5, "sector": "consumer", "industry": "baijiu"},
            {"stock_code": "000858", "stock_name": "Wuliangye", "weight": 7.2, "sector": "consumer", "industry": "baijiu"},
            {"stock_code": "300750", "stock_name": "CATL", "weight": 6.8, "sector": "manufacturing", "industry": "battery"},
        ],
        "sectors": [
            {"industry": "baijiu", "weight": 16.7},
            {"industry": "battery", "weight": 6.8},
        ],
    }


@pytest.fixture
def multi_fund_data():
    return [
        {
            "code": "110011",
            "name": "Fund A",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "600519", "stock_name": "Moutai", "weight": 9.5, "sector": "consumer", "industry": "baijiu"},
                {"stock_code": "000858", "stock_name": "Wuliangye", "weight": 7.2, "sector": "consumer", "industry": "baijiu"},
            ],
            "sectors": [{"industry": "baijiu", "weight": 16.7}],
        },
        {
            "code": "006123",
            "name": "Fund B",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "600519", "stock_name": "Moutai", "weight": 8.0, "sector": "consumer", "industry": "baijiu"},
                {"stock_code": "300750", "stock_name": "CATL", "weight": 6.0, "sector": "manufacturing", "industry": "battery"},
            ],
            "sectors": [
                {"industry": "baijiu", "weight": 8.0},
                {"industry": "battery", "weight": 6.0},
            ],
        },
    ]


class TestEnumSafeQueries:
    def test_get_entity_chain_returns_holdings(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        result = get_entity_chain(kg, "110011")
        assert result["fund"]["code"] == "110011"
        assert len(result["holdings"]) >= 1

    def test_query_exposure_returns_industries(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        result = query_exposure(kg, "110011")
        assert "industries" in result
        assert "themes" in result

    def test_expand_theme_returns_industries(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        result = expand_theme(kg, "baijiu")
        assert result["theme"] == "baijiu"

    def test_find_related_events_empty_without_events(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        result = find_related_events(kg, "fund:110011")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_find_related_events_with_enriched_events(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        event = EventNode(
            event_id="E001",
            event_type="regulatory",
            subtype="policy_change",
            polarity=0.8,
            magnitude=0.6,
        )
        enrich_with_events(kg.graph, [event], ["stock:600519"])

        result = find_related_events(kg, "fund:110011")
        assert len(result) >= 1
        assert result[0]["event_id"] == "E001"
        assert result[0]["polarity"] == 0.8

    def test_find_related_events_for_stock(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        event = EventNode(
            event_id="E002",
            event_type="earnings",
            polarity=-0.5,
            magnitude=0.7,
        )
        enrich_with_events(kg.graph, [event], ["stock:000858"])

        result = find_related_events(kg, "stock:000858")
        assert len(result) >= 1
        assert result[0]["event_id"] == "E002"
        assert result[0]["polarity"] == -0.5

    def test_enum_comparison_not_string(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        for _, _, data in kg.graph.edges(data=True):
            edge = data.get("edge_data")
            if edge:
                assert isinstance(edge.edge_type, KGEdgeType)


class TestBuilderCacheConsistency:
    def test_build_from_holdings_creates_graph(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        assert G is not None
        assert G.has_node("fund:110011")
        assert G.has_node("stock:600519")

    def test_multi_fund_holdings(self, multi_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(multi_fund_data[0])
        G = builder.refresh(G, multi_fund_data[1:])
        assert G.has_node("fund:110011")
        assert G.has_node("fund:006123")
        assert G.has_node("stock:600519")

    def test_refresh_adds_new_fund(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        new_fund = {
            "code": "006123",
            "name": "New Fund",
            "fund_type": "bond",
            "holdings": [
                {"stock_code": "601318", "stock_name": "Ping An", "weight": 5.0, "sector": "finance", "industry": "insurance"},
            ],
            "sectors": [{"industry": "insurance", "weight": 5.0}],
        }
        G2 = builder.refresh(G, [new_fund])
        assert G2.has_node("fund:006123")
        assert G2.has_node("stock:601318")

    def test_save_load_roundtrip(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_kg.pkl")
            builder.save(G, path)
            loaded = builder.load(path)
            assert set(loaded.nodes) == set(G.nodes)
            assert set(loaded.edges) == set(G.edges)

    def test_cache_key_stability(self):
        key1 = KnowledgeGraphBuilder.cache_key(["110011", "006123"])
        key2 = KnowledgeGraphBuilder.cache_key(["006123", "110011"])
        assert key1 == key2
        assert key1.startswith("kg_cache_")

    def test_cache_save_load(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, kg_cache_key(["110011"]))
            save_kg_cache(G, path)
            loaded = load_kg_cache(path, max_age_hours=1)
            assert loaded is not None
            assert set(loaded.nodes) == set(G.nodes)

    def test_cache_expired(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, kg_cache_key(["110011"]))
            save_kg_cache(G, path)
            loaded = load_kg_cache(path, max_age_hours=0)
            assert loaded is None


class TestEventRelationSupport:
    def test_fund_stock_event_chain(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        event = EventNode(
            event_id="E001",
            event_type="regulatory",
            polarity=0.8,
            magnitude=0.6,
        )
        enrich_with_events(kg.graph, [event], ["stock:600519"])
        assert kg.graph.has_node("event:E001")

        events = find_related_events(kg, "fund:110011")
        assert any(e["event_id"] == "E001" for e in events)

    def test_event_impact_chain(self, sample_fund_data):
        builder = KnowledgeGraphBuilder()
        G = builder.build_from_holdings(sample_fund_data)
        event = EventNode(
            event_id="E003",
            event_type="earnings",
            polarity=-0.9,
            magnitude=0.8,
        )
        enrich_with_events(G, [event], ["stock:600519"])
        impact = builder.get_impact_chain(G, "E003", "110011")
        assert impact["total_polarity"] != 0.0
        assert len(impact["paths"]) >= 1

    def test_multiple_events_for_stock(self, sample_fund_data):
        kg = KnowledgeGraph()
        kg.build_from_holdings(sample_fund_data)
        events = [
            EventNode(event_id="E01", event_type="regulatory", polarity=0.5, magnitude=0.3),
            EventNode(event_id="E02", event_type="earnings", polarity=-0.7, magnitude=0.6),
        ]
        enrich_with_events(kg.graph, events, ["stock:600519"])
        result = find_related_events(kg, "stock:600519")
        assert len(result) >= 2
