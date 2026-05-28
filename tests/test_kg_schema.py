"""Tests for Knowledge Graph schema and industry mapping."""
import pickle
import pytest
from src.kg.schema import (
    KGNodeType, KGEdgeType, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.kg.industry_map import (
    INDUSTRY_THEME_MAP, THEME_KEYWORDS,
    get_themes_for_industry, get_keywords_for_theme, get_all_themes, get_all_industries,
)


class TestKGSchema:
    def test_node_types_enum(self):
        assert KGNodeType.FUND.value == "fund"
        assert KGNodeType.STOCK.value == "stock"
        assert KGNodeType.INDUSTRY.value == "industry"
        assert KGNodeType.THEME.value == "theme"
        assert KGNodeType.EVENT.value == "event"
        assert KGNodeType.MACRO_FACTOR.value == "macro_factor"

    def test_edge_types_enum(self):
        assert KGEdgeType.HOLDS.value == "holds"
        assert KGEdgeType.BELONGS_TO.value == "belongs_to"
        assert KGEdgeType.IN_THEME.value == "in_theme"
        assert KGEdgeType.IMPACTS.value == "impacts"
        assert KGEdgeType.CORRELATES_WITH.value == "correlates"
        assert KGEdgeType.EXPOSES.value == "exposes"

    def test_fund_node_creation(self):
        node = FundNode(code="110011", name="易方达中小盘混合", fund_type="hybrid", style="growth")
        assert node.node_type == KGNodeType.FUND
        assert node.code == "110011"
        assert node.id == "fund:110011"
        assert node.style == "growth"

    def test_stock_node_creation(self):
        node = StockNode(code="600519", name="贵州茅台", sector="白酒", industry="食品饮料")
        assert node.node_type == KGNodeType.STOCK
        assert node.code == "600519"
        assert node.id == "stock:600519"

    def test_event_node_creation(self):
        node = EventNode(
            event_id="evt_001",
            event_type="rate_change",
            subtype="fed_rate_decision",
            date="2026-05-27",
            polarity=-0.7,
            magnitude=0.8,
            time_horizon="medium",
            description="美联储维持利率不变"
        )
        assert node.node_type == KGNodeType.EVENT
        assert node.polarity == -0.7
        assert node.magnitude == 0.8
        assert node.id == "event:evt_001"

    def test_kg_edge_creation(self):
        edge = KGEdge(
            source="110011",
            target="600519",
            edge_type=KGEdgeType.HOLDS,
            weight=0.095
        )
        assert edge.edge_type == KGEdgeType.HOLDS
        assert edge.weight == pytest.approx(0.095)
        assert edge.source == "110011"

    def test_edge_with_polarity(self):
        edge = KGEdge(
            source="evt_001",
            target="600519",
            edge_type=KGEdgeType.IMPACTS,
            polarity=-0.5,
            magnitude=0.7
        )
        assert edge.polarity == -0.5

    def test_industry_node(self):
        node = IndustryNode(code="sw_food_beverage", name="食品饮料", sw_code="801120")
        assert node.node_type == KGNodeType.INDUSTRY
        assert node.id == "industry:sw_food_beverage"

    def test_theme_node(self):
        node = ThemeNode(name="AI算力", keywords=["人工智能", "算力", "GPU", "光模块"])
        assert node.node_type == KGNodeType.THEME
        assert len(node.keywords) == 4
        assert node.id == "theme:AI算力"

    def test_macro_factor_node(self):
        node = MacroFactorNode(name="利率", factor_type="interest_rate", direction="rising")
        assert node.node_type == KGNodeType.MACRO_FACTOR
        assert node.id == "macro:利率"

    def test_fund_node_equality(self):
        node1 = FundNode(code="110011", name="test")
        node2 = FundNode(code="110011", name="test")
        assert node1 == node2

    def test_fund_node_inequality(self):
        node1 = FundNode(code="110011", name="test1")
        node2 = FundNode(code="110012", name="test2")
        assert node1 != node2

    def test_fund_node_pickle_roundtrip(self):
        """Serialize FundNode to pickle and back -- id, code, type survive."""
        node = FundNode(code="110011", name="易方达中小盘混合", fund_type="hybrid", style="growth")
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "fund:110011"
        assert restored.code == "110011"
        assert restored.node_type == KGNodeType.FUND

    def test_stock_node_pickle_roundtrip(self):
        """Serialize StockNode to pickle and back."""
        node = StockNode(code="600519", name="贵州茅台", sector="白酒", industry="食品饮料")
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "stock:600519"
        assert restored.code == "600519"

    def test_industry_node_pickle_roundtrip(self):
        """Serialize IndustryNode to pickle and back."""
        node = IndustryNode(code="sw_food_beverage", name="食品饮料", sw_code="801120")
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "industry:sw_food_beverage"
        assert restored.name == "食品饮料"

    def test_theme_node_pickle_roundtrip(self):
        """Serialize ThemeNode (with keywords list) to pickle and back."""
        node = ThemeNode(name="AI算力", keywords=["人工智能", "算力", "GPU", "光模块"])
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "theme:AI算力"
        assert restored.keywords == ["人工智能", "算力", "GPU", "光模块"]

    def test_event_node_pickle_roundtrip(self):
        """Serialize EventNode to pickle and back -- polarity, magnitude survive."""
        node = EventNode(
            event_id="evt_001",
            event_type="earnings_surprise",
            subtype="positive",
            date="2026-05-27",
            polarity=0.8,
            magnitude=0.6,
            time_horizon="short",
            description="Q1 beat",
        )
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "event:evt_001"
        assert restored.polarity == 0.8
        assert restored.magnitude == 0.6

    def test_macro_factor_node_pickle_roundtrip(self):
        """Serialize MacroFactorNode to pickle and back."""
        node = MacroFactorNode(name="利率", factor_type="interest_rate", direction="rising")
        data = pickle.dumps(node)
        restored = pickle.loads(data)
        assert restored == node
        assert restored.id == "macro:利率"
        assert restored.factor_type == "interest_rate"

    def test_kg_edge_pickle_roundtrip(self):
        """Serialize KGEdge with optional fields to pickle and back."""
        edge = KGEdge(
            source="fund:110011",
            target="stock:600519",
            edge_type=KGEdgeType.HOLDS,
            weight=9.5,
            polarity=0.3,
            magnitude=0.7,
        )
        data = pickle.dumps(edge)
        restored = pickle.loads(data)
        assert restored == edge
        assert restored.edge_type == KGEdgeType.HOLDS
        assert restored.weight == pytest.approx(9.5)
        assert restored.polarity == 0.3


class TestIndustryMap:
    def test_industry_to_theme_mapping(self):
        assert len(INDUSTRY_THEME_MAP) >= 20
        assert len(THEME_KEYWORDS) >= 10

    def test_get_themes_for_industry(self):
        themes = get_themes_for_industry("电子")
        assert isinstance(themes, list)
        assert len(themes) >= 1
        # Electronics maps to semiconductor/AI themes
        assert "半导体" in themes or "AI算力" in themes

    def test_get_themes_for_unknown_industry(self):
        themes = get_themes_for_industry("未知行业")
        assert themes == []

    def test_get_keywords_for_theme(self):
        keywords = get_keywords_for_theme("半导体")
        assert isinstance(keywords, list)
        assert len(keywords) >= 2
        assert "芯片" in keywords

    def test_get_keywords_for_unknown_theme(self):
        keywords = get_keywords_for_theme("未知主题")
        assert keywords == []

    def test_get_all_themes(self):
        themes = get_all_themes()
        assert isinstance(themes, list)
        assert len(themes) >= 20

    def test_get_all_industries(self):
        industries = get_all_industries()
        assert isinstance(industries, list)
        assert len(industries) >= 20

    def test_theme_keywords_non_empty(self):
        for theme, keywords in THEME_KEYWORDS.items():
            assert len(keywords) >= 2, f"Theme '{theme}' has fewer than 2 keywords: {keywords}"
