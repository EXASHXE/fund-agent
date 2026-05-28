"""Tests for Knowledge Graph builder, query, and enrichment."""
import pytest
from src.kg.graph import KnowledgeGraphBuilder
from src.kg.schema import KGNodeType, KGEdgeType, EventNode
from src.kg.enrichment import enrich_with_events


@pytest.fixture
def sample_fund_data():
    return {
        "code": "110011",
        "name": "易方达中小盘混合",
        "fund_type": "hybrid",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            {"stock_code": "601318", "stock_name": "中国平安", "weight": 5.1},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
            {"industry": "金融", "weight": 15.2},
        ],
    }


class TestKnowledgeGraphBuilder:
    def test_build_from_holdings_creates_fund_node(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        fund_id = f"fund:{sample_fund_data['code']}"
        assert graph.has_node(fund_id)
        assert graph.nodes[fund_id]["data"].node_type == KGNodeType.FUND

    def test_build_from_holdings_creates_stock_nodes(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        stock_nodes = [n for n in graph.nodes if n.startswith("stock:")]
        assert len(stock_nodes) == 3
        for node_id in stock_nodes:
            assert graph.nodes[node_id]["data"].node_type == KGNodeType.STOCK

    def test_build_from_holdings_creates_hold_edges(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        hold_edges = []
        for src, dst, data in graph.edges(data=True):
            edge = data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.HOLDS:
                hold_edges.append(edge)
        assert len(hold_edges) == 3
        maotai_edges = [e for e in hold_edges if e.target == "stock:600519"]
        assert len(maotai_edges) == 1
        assert maotai_edges[0].weight == pytest.approx(9.5)

    def test_build_from_holdings_creates_industry_nodes(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        industry_nodes = [n for n in graph.nodes if n.startswith("industry:")]
        assert len(industry_nodes) >= 2

    def test_query_relevance_for_fund_news(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        news = {"title": "贵州茅台发布年报", "entities": ["600519"]}
        relevance = kg.query_relevance(graph, sample_fund_data["code"], news)
        assert relevance > 0.3

    def test_query_relevance_for_unrelated_news(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        news = {"title": "某生物医药公司上市", "entities": ["300999"]}
        relevance = kg.query_relevance(graph, sample_fund_data["code"], news)
        assert relevance < 0.2

    def test_get_fund_exposure(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        exposure = kg.get_fund_exposure(graph, sample_fund_data["code"])
        assert "industries" in exposure
        assert "themes" in exposure
        assert any("食品饮料" in ind for ind in exposure["industries"])

    def test_enrich_with_events(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        event = EventNode(
            event_id="evt_001",
            event_type="earnings_surprise",
            subtype="positive",
            date="2026-05-27",
            polarity=0.8,
            magnitude=0.6,
            time_horizon="short",
            description="贵州茅台Q1净利润超预期20%"
        )

        graph = enrich_with_events(graph, [event], affected_entities=["stock:600519"])
        event_nodes = [n for n in graph.nodes if n.startswith("event:")]
        assert len(event_nodes) == 1
        assert graph.nodes["event:evt_001"]["data"].event_type == "earnings_surprise"

        impact_edges = []
        for src, dst, data in graph.edges(data=True):
            edge = data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.IMPACTS:
                impact_edges.append(edge)
        assert len(impact_edges) == 1
        assert impact_edges[0].polarity == pytest.approx(0.8)

    def test_get_impact_chain(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        event = EventNode(
            event_id="evt_001",
            event_type="earnings_surprise",
            subtype="positive",
            date="2026-05-27",
            polarity=0.8,
            magnitude=0.6,
            time_horizon="short",
            description="贵州茅台Q1净利润超预期"
        )
        graph = enrich_with_events(graph, [event], affected_entities=["stock:600519"])

        impact = kg.get_impact_chain(graph, "evt_001", sample_fund_data["code"])
        assert impact["total_polarity"] != 0
        assert len(impact["paths"]) >= 1