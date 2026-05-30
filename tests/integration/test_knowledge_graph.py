"""Tests for KnowledgeGraph context layer wrappers (src/graph/)."""
import os
import tempfile
import time

import pytest
import networkx as nx

from src.graph.entities import FundNode, KGNodeType
from src.graph.relations import KGEdgeType
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.queries import (
    get_entity_chain,
    query_exposure,
    expand_theme,
    find_related_events,
)
from src.graph.cache import save_kg_cache, load_kg_cache, kg_cache_key


# ------------------------------------------------------------------------ fixtures

@pytest.fixture
def sample_fund_data():
    return {
        "110011": {
            "code": "110011",
            "name": "易方达中小盘",
            "fund_type": "混合型",
            "holdings": [
                {"code": "600519", "name": "贵州茅台", "weight": 8.5,
                 "industry": "食品饮料", "sector": "消费"},
                {"code": "000858", "name": "五粮液", "weight": 7.2,
                 "industry": "食品饮料", "sector": "消费"},
                {"code": "300750", "name": "宁德时代", "weight": 6.8,
                 "industry": "电力设备", "sector": "新能源"},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 30.5},
                {"industry": "电力设备", "weight": 22.1},
            ],
        }
    }


@pytest.fixture
def kg_with_data(sample_fund_data):
    """Build a KnowledgeGraph from sample data."""
    kg = KnowledgeGraph()
    kg.build_from_holdings(sample_fund_data)
    return kg


# ---------------------------------------------------------- Phase B & C: re-exports

def test_entity_re_exports():
    """FundNode and KGNodeType must be importable from src.graph.entities."""
    assert FundNode(code="000001", name="test").code == "000001"
    assert KGNodeType.FUND.value == "fund"


def test_relation_re_exports():
    """KGEdgeType must be importable from src.graph.relations."""
    assert KGEdgeType.HOLDS.value == "holds"
    assert KGEdgeType.BELONGS_TO.value == "belongs_to"


# -------------------------------------------------------------------- Phase D: KG

def test_kg_build_from_holdings(kg_with_data):
    """Build KG from holdings — verify graph exists and has expected nodes."""
    g = kg_with_data.graph
    assert g is not None, "Graph should not be None after build"
    assert isinstance(g, nx.DiGraph)
    assert g.has_node("fund:110011"), "Fund node must be present"
    assert g.has_node("stock:600519"), "Stock node must be present"

    # Verify fund node data
    fund_data = g.nodes["fund:110011"]["data"]
    assert fund_data.name == "易方达中小盘"
    assert fund_data.fund_type == "混合型"


def test_kg_save_load_roundtrip(kg_with_data):
    """Save then load — loaded graph should have same nodes and edges."""
    g = kg_with_data.graph
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        tmp_path = f.name

    try:
        kg_with_data.save(tmp_path)
        assert os.path.exists(tmp_path), "Save file must exist on disk"

        kg2 = KnowledgeGraph()
        loaded = kg2.load(tmp_path)
        assert isinstance(loaded, nx.DiGraph)

        # Same nodes
        assert set(loaded.nodes) == set(g.nodes), "Loaded graph must have same nodes"
        # Same edges
        assert set(loaded.edges) == set(g.edges), "Loaded graph must have same edges"
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------- Phase E: queries

def test_get_entity_chain(kg_with_data):
    """Entity chain must return a dict with 'fund' key."""
    result = get_entity_chain(kg_with_data, "110011")
    assert isinstance(result, dict)
    assert result.get("fund", {}).get("code") == "110011"
    assert isinstance(result.get("holdings"), list)


def test_get_entity_chain_empty_kg():
    """Entity chain on empty KG must return dict without holdings."""
    empty_kg = KnowledgeGraph()
    result = get_entity_chain(empty_kg, "110011")
    assert result == {"fund": "110011", "chain": []}


def test_query_exposure(kg_with_data):
    """Query exposure must return industries and themes."""
    result = query_exposure(kg_with_data, "110011")
    assert isinstance(result, dict)
    assert "industries" in result
    assert "themes" in result


def test_query_exposure_empty_kg():
    """Query exposure on empty KG must return an empty dict."""
    empty_kg = KnowledgeGraph()
    result = query_exposure(empty_kg, "110011")
    assert result == {"fund": "110011", "exposure": {}}


def test_expand_theme(kg_with_data):
    """Theme diffusion must be callable and return a dict."""
    result = expand_theme(kg_with_data, "白酒")
    assert isinstance(result, dict)
    assert "theme" in result
    assert result["theme"] == "白酒"


def test_find_related_events(kg_with_data):
    """find_related_events must return a list."""
    result = find_related_events(kg_with_data, "fund:110011")
    assert isinstance(result, list)

    # Also test for a stock entity
    result2 = find_related_events(kg_with_data, "stock:600519")
    assert isinstance(result2, list)


# ----------------------------------------------------------------- Phase F: cache

def test_cache_key():
    """Cache key must be deterministic regardless of input order."""
    k1 = kg_cache_key(["110011", "006123"])
    k2 = kg_cache_key(["006123", "110011"])
    assert k1 == k2
    assert k1.startswith("kg_")
    assert k1.endswith(".pkl")
    assert "006123" in k1
    assert "110011" in k1


def test_cache_load_expired():
    """Expired cache must return None."""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        tmp_path = f.name

    try:
        from datetime import datetime
        # Create a dummy file
        save_kg_cache({"test": True}, tmp_path)
        assert os.path.exists(tmp_path)

        # Artificially make it old (set mtime to 48 hours ago)
        old_time = int(time.time() - 48 * 3600)
        os.utime(tmp_path, (old_time, old_time))

        # With max_age_hours=24, this should be expired
        stale = load_kg_cache(tmp_path, max_age_hours=24)
        assert stale is None, "Expired cache should return None"

        # But it should load with a larger max_age
        fresh = load_kg_cache(tmp_path, max_age_hours=72)
        assert fresh is not None, "Should load with generous max_age"
        assert fresh == {"test": True}
    finally:
        os.unlink(tmp_path)
