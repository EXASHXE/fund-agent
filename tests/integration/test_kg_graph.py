"""Tests for Knowledge Graph builder, query, and enrichment."""
import pytest
import os
import pickle
import networkx as nx

from src.graph.builder import KnowledgeGraphBuilder
from src.graph.schema import KGNodeType, KGEdgeType, KGEdge, EventNode, StockNode, FundNode, IndustryNode, MacroFactorNode, FundNode
from src.graph.enrichment import enrich_with_events
from src.graph.diff import GraphDiff


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

    def test_build_from_holdings_empty_industry_name(self):
        """Sector with empty industry name is skipped gracefully."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [
                {"industry": "", "weight": 0.0},
            ],
        }
        graph = kg.build_from_holdings(fund_data)
        # No industry node should exist for the empty name
        assert graph.has_node("fund:110011")
        assert graph.has_node("stock:600519")

    def test_build_from_holdings_stock_explicit_industry(self):
        """Holding with explicit 'industry' field creates BELONGS_TO edge."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "茅台", "weight": 5.0, "industry": "食品饮料"},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 30.0},
            ],
        }
        graph = kg.build_from_holdings(fund_data)
        stock_id = "stock:600519"
        industry_id = "industry:sw_食品饮料"
        # Should have BELONGS_TO edge from stock to industry
        edge_data = graph.get_edge_data(stock_id, industry_id)
        assert edge_data is not None
        edge = edge_data.get("edge_data")
        assert edge is not None
        assert edge.edge_type == KGEdgeType.BELONGS_TO

    def test_build_from_holdings_stock_no_industry_falls_back(self):
        """Holding without explicit industry falls back to first sector."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "茅台", "weight": 5.0},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 30.0},
            ],
        }
        graph = kg.build_from_holdings(fund_data)
        stock_id = "stock:600519"
        industry_id = "industry:sw_食品饮料"
        edge_data = graph.get_edge_data(stock_id, industry_id)
        assert edge_data is not None
        edge = edge_data.get("edge_data")
        assert edge is not None
        assert edge.edge_type == KGEdgeType.BELONGS_TO

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

    def test_query_relevance_nonexistent_fund(self, sample_fund_data):
        """Query relevance for a fund not in the graph returns 0."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        relevance = kg.query_relevance(graph, "999999", {"title": "test", "entities": []})
        assert relevance == 0.0

    def test_query_relevance_keyword_theme_hit(self, sample_fund_data):
        """Theme keyword match in title returns partial theme_hit (0.5)."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # "白酒" is a keyword for a theme linked to 食品饮料
        news = {"title": "白酒行业复苏明显", "entities": []}
        relevance = kg.query_relevance(graph, sample_fund_data["code"], news)
        # Should get some relevance from theme keyword match
        assert relevance > 0.0

    def test_get_fund_exposure(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        exposure = kg.get_fund_exposure(graph, sample_fund_data["code"])
        assert "industries" in exposure
        assert "themes" in exposure
        assert any("食品饮料" in ind for ind in exposure["industries"])

    def test_get_fund_exposure_nonexistent_fund(self, sample_fund_data):
        """Non-existent fund returns empty exposure."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        exposure = kg.get_fund_exposure(graph, "999999")
        assert exposure == {"industries": [], "themes": [], "macro_factors": []}

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

    def test_get_impact_chain_nonexistent_event(self, sample_fund_data):
        """Non-existent event ID returns empty impact chain."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        impact = kg.get_impact_chain(graph, "evt_nonexistent", sample_fund_data["code"])
        assert impact["total_polarity"] == 0.0
        assert impact["total_magnitude"] == 0.0
        assert impact["paths"] == []

    def test_get_impact_chain_nonexistent_fund(self, sample_fund_data):
        """Non-existent fund code returns empty impact chain."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        impact = kg.get_impact_chain(graph, "evt_001", "999999")
        assert impact["total_polarity"] == 0.0

    def test_serialization_roundtrip(self, sample_fund_data, tmp_path):
        """Build graph, save to pickle, load back, verify structure and metadata."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        save_path = os.path.join(str(tmp_path), "test_kg.pkl")
        kg.save(graph, save_path)

        loaded_graph = KnowledgeGraphBuilder.load(save_path)

        # Structural equivalence
        assert loaded_graph.number_of_nodes() == graph.number_of_nodes()
        assert loaded_graph.number_of_edges() == graph.number_of_edges()

        # Metadata survived
        assert loaded_graph.graph["version"] == 1
        assert loaded_graph.graph["funds_indexed"] == ["110011"]
        assert "generated_at" in loaded_graph.graph

        # Node data survived roundtrip
        fund_id = "fund:110011"
        assert loaded_graph.nodes[fund_id]["data"].code == "110011"
        assert loaded_graph.nodes[fund_id]["data"].node_type == KGNodeType.FUND

        # Edge data survived
        stock_id = "stock:600519"
        edge_data = loaded_graph.get_edge_data(fund_id, stock_id)
        assert edge_data is not None
        assert edge_data["edge_data"].weight == pytest.approx(9.5)

        # Calling save again increments version
        kg.save(loaded_graph, save_path)
        reloaded = KnowledgeGraphBuilder.load(save_path)
        assert reloaded.graph["version"] == 2

    def test_cache_key_determinism(self):
        """Same fund codes in different order produce identical cache keys."""
        codes_a = ["110011", "006123"]
        codes_b = ["006123", "110011"]
        key_a = KnowledgeGraphBuilder.cache_key(codes_a)
        key_b = KnowledgeGraphBuilder.cache_key(codes_b)
        assert key_a == key_b
        assert key_a == "kg_cache_006123_110011.pkl"

    def test_cache_key_uniqueness(self):
        """Different fund codes produce different cache keys."""
        key1 = KnowledgeGraphBuilder.cache_key(["110011"])
        key2 = KnowledgeGraphBuilder.cache_key(["006123"])
        assert key1 != key2
        assert key1 == "kg_cache_110011.pkl"
        assert key2 == "kg_cache_006123.pkl"

    def test_cache_key_empty_list(self):
        """Empty fund codes list produces predictable cache key."""
        key = KnowledgeGraphBuilder.cache_key([])
        assert key == "kg_cache_.pkl"

    def test_save_creates_directories(self, sample_fund_data, tmp_path):
        """Save to a path with non-existent parent dirs creates them."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        deep_path = os.path.join(str(tmp_path), "subdir", "nested", "cache.pkl")
        kg.save(graph, deep_path)
        assert os.path.exists(deep_path)

        loaded = KnowledgeGraphBuilder.load(deep_path)
        assert loaded.graph["version"] >= 1
        assert loaded.has_node("fund:110011")

    def test_load_corrupt_pickle(self, tmp_path):
        """Loading a corrupt pickle file raises UnpicklingError."""
        corrupt_path = os.path.join(str(tmp_path), "corrupt.pkl")
        with open(corrupt_path, "wb") as f:
            f.write(b"\x00\x01\x02\xffthis is not valid pickle data\xfe\xfd")

        with pytest.raises((pickle.UnpicklingError, EOFError, TypeError)):
            KnowledgeGraphBuilder.load(corrupt_path)

    def test_load_type_error_non_digraph(self, tmp_path):
        """Loading a pickle that is not an nx.DiGraph raises TypeError."""
        non_digraph_path = os.path.join(str(tmp_path), "not_digraph.pkl")
        with open(non_digraph_path, "wb") as f:
            pickle.dump({"this": "is a dict, not a DiGraph"}, f)

        with pytest.raises(TypeError, match="Expected nx.DiGraph"):
            KnowledgeGraphBuilder.load(non_digraph_path)

    def test_load_invalid_file(self, tmp_path):
        """Loading a non-pickle file raises an error."""
        invalid_path = os.path.join(str(tmp_path), "not_a_pickle.txt")
        with open(invalid_path, "w") as f:
            f.write("this is definitely not a pickle file")

        with pytest.raises((pickle.UnpicklingError, TypeError, EOFError)):
            KnowledgeGraphBuilder.load(invalid_path)

    def test_load_nonexistent_file(self, tmp_path):
        """Loading a file that does not exist raises FileNotFoundError."""
        nonexistent = os.path.join(str(tmp_path), "does_not_exist.pkl")
        with pytest.raises(FileNotFoundError, match="Knowledge graph file not found"):
            KnowledgeGraphBuilder.load(nonexistent)


class TestGraphDiffSummary:
    """Tests for GraphDiff.is_empty() and summary()."""

    def test_diff_empty_summary(self):
        diff = GraphDiff([], [], [], [], [])
        assert diff.is_empty()
        assert diff.summary() == "no changes"

    def test_diff_added_nodes_summary(self):
        diff = GraphDiff(added_nodes=["fund:002"], removed_nodes=[], modified_nodes=[],
                         added_edges=[], removed_edges=[])
        assert not diff.is_empty()
        assert "nodes" in diff.summary()
        assert "1" in diff.summary()

    def test_diff_removed_nodes_summary(self):
        diff = GraphDiff(added_nodes=[], removed_nodes=["fund:001"], modified_nodes=[],
                         added_edges=[], removed_edges=[])
        assert not diff.is_empty()
        assert "nodes" in diff.summary()

    def test_diff_modified_nodes_summary(self):
        diff = GraphDiff(added_nodes=[], removed_nodes=[], modified_nodes=["stock:001"],
                         added_edges=[], removed_edges=[])
        assert not diff.is_empty()
        assert "nodes" in diff.summary()

    def test_diff_added_edges_summary(self):
        diff = GraphDiff(added_nodes=[], removed_nodes=[], modified_nodes=[],
                         added_edges=[("a", "b")], removed_edges=[])
        assert not diff.is_empty()
        assert "edges" in diff.summary()

    def test_diff_removed_edges_summary(self):
        diff = GraphDiff(added_nodes=[], removed_nodes=[], modified_nodes=[],
                         added_edges=[], removed_edges=[("c", "d")])
        assert not diff.is_empty()
        assert "edges" in diff.summary()

    def test_diff_all_categories_summary(self):
        diff = GraphDiff(
            added_nodes=["fund:003"],
            removed_nodes=["fund:001"],
            modified_nodes=["stock:600519"],
            added_edges=[("fund:003", "stock:600519")],
            removed_edges=[("fund:001", "stock:000858")],
        )
        summary = diff.summary()
        assert "no changes" not in summary
        assert "+" in summary
        assert "-" in summary
        assert "~" in summary


class TestEntityChain:
    """Tests for KnowledgeGraphBuilder.entity_chain()."""

    def test_entity_chain_traces_full_path(self, sample_fund_data):
        """fund → at least one stock → industry → theme."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        result = KnowledgeGraphBuilder.entity_chain(graph, sample_fund_data["code"])

        assert result["fund"]["code"] == "110011"
        assert result["fund"]["name"] == "易方达中小盘混合"
        assert len(result["holdings"]) == 3

        # Every holding should have a stock key
        stock_codes = [h["stock"]["code"] for h in result["holdings"]]
        assert "600519" in stock_codes

        # At least one holding traces to industry 食品饮料
        industries = [h["industry"].get("name", "") for h in result["holdings"]]
        assert any("食品饮料" in ind for ind in industries)

        # At least one holding traces to themes 消费/白酒
        all_themes = []
        for h in result["holdings"]:
            all_themes.extend(t["name"] for t in h["themes"])
        assert "消费" in all_themes or "白酒" in all_themes

        # Exposure map populated
        assert "食品饮料" in result["exposure"]
        assert isinstance(result["exposure"]["食品饮料"], list)
        assert len(result["exposure"]["食品饮料"]) >= 1

    def test_entity_chain_empty_holdings(self):
        """Fund with no holdings returns empty lists properly."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "999999",
            "name": "空仓基金",
            "fund_type": "hybrid",
            "holdings": [],
            "sectors": [],
        }
        graph = kg.build_from_holdings(fund_data)
        result = KnowledgeGraphBuilder.entity_chain(graph, "999999")

        assert result["fund"]["code"] == "999999"
        assert result["fund"]["name"] == "空仓基金"
        assert result["holdings"] == []
        assert result["exposure"] == {}

    def test_entity_chain_nonexistent_fund(self):
        """Non-existent fund code returns empty structure."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings({"code": "000000", "holdings": [], "sectors": []})
        result = KnowledgeGraphBuilder.entity_chain(graph, "999999")
        assert result["fund"] == {}
        assert result["holdings"] == []
        assert result["exposure"] == {}

    def test_entity_chain_multiple_stocks(self):
        """Fund with 5+ holdings traces all stocks, industries, and themes."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "多持仓基金",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 8.0, "industry": "食品饮料"},
                {"stock_code": "000858", "stock_name": "五粮液", "weight": 6.5, "industry": "食品饮料"},
                {"stock_code": "300750", "stock_name": "宁德时代", "weight": 5.0, "industry": "电力设备"},
                {"stock_code": "601318", "stock_name": "中国平安", "weight": 4.0, "industry": "金融"},
                {"stock_code": "002415", "stock_name": "海康威视", "weight": 3.0, "industry": "计算机"},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 25.0},
                {"industry": "电力设备", "weight": 15.0},
                {"industry": "金融", "weight": 10.0},
                {"industry": "计算机", "weight": 8.0},
            ],
        }
        graph = kg.build_from_holdings(fund_data)
        result = KnowledgeGraphBuilder.entity_chain(graph, "110011")

        assert len(result["holdings"]) == 5
        stock_codes = [h["stock"]["code"] for h in result["holdings"]]
        assert len(stock_codes) == 5
        assert "600519" in stock_codes
        assert "300750" in stock_codes
        assert "002415" in stock_codes

        # At least some holdings have industry + themes
        holdings_with_industry = [h for h in result["holdings"] if h["industry"]]
        assert len(holdings_with_industry) >= 1

        # Exposure map should have multiple industries (at least 食品饮料 + others)
        assert len(result["exposure"]) >= 2


class TestThemeDiffusion:
    """Tests for KnowledgeGraphBuilder.theme_diffusion()."""

    def test_theme_diffusion_finds_exposed_funds(self, sample_fund_data):
        """Theme → funds connected through industry."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        result = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒")

        assert result["theme"] == "白酒"
        assert len(result["industries"]) >= 1
        industry_names = [ind["industry_name"] for ind in result["industries"]]
        assert "食品饮料" in industry_names

        assert len(result["stocks"]) >= 1
        stock_codes = [s["stock_code"] for s in result["stocks"]]
        assert "600519" in stock_codes or "000858" in stock_codes

        assert len(result["exposed_funds"]) >= 1
        fund_codes_found = [f["fund_code"] for f in result["exposed_funds"]]
        assert "110011" in fund_codes_found
        # overlap_pct should be > 0 for the matching fund
        for f in result["exposed_funds"]:
            if f["fund_code"] == "110011":
                assert f["overlap_pct"] > 0

    def test_theme_diffusion_nonexistent_theme(self):
        """Non-existent theme returns empty structure."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings({"code": "000000", "holdings": [], "sectors": []})
        result = KnowledgeGraphBuilder.theme_diffusion(graph, "nonexistent_theme_xyz")
        assert result["theme"] == "nonexistent_theme_xyz"
        assert result["industries"] == []
        assert result["stocks"] == []
        assert result["exposed_funds"] == []

    def test_theme_diffusion_no_funds(self):
        """Theme with industries but no connected funds returns empty funds."""
        # Build graph with a theme that exists but no fund holds stocks in it
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings({"code": "000000", "holdings": [], "sectors": []})
        # "白酒" theme exists via 食品饮料 industry, but no fund has holdings
        result = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒")
        assert result["theme"] == "白酒"
        # It might have industries (from the industry map), but no stocks or funds
        # since no fund was built with actual holdings
        assert result["stocks"] == []
        assert result["exposed_funds"] == []

    def test_theme_diffusion_max_depth_1(self, sample_fund_data):
        """max_depth=1 returns only industries, no stocks or funds."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        result_depth1 = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒", max_depth=1)
        result_depth2 = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒", max_depth=2)

        # Depth 1 has industries
        assert len(result_depth1["industries"]) >= 1
        # Depth 1 has no stocks or funds
        assert result_depth1["stocks"] == []
        assert result_depth1["exposed_funds"] == []

        # Depth 2 has everything
        assert len(result_depth2["stocks"]) >= 1
        assert len(result_depth2["exposed_funds"]) >= 1

    def test_theme_diffusion_max_depth_2(self, sample_fund_data):
        """max_depth=2 returns full chain including stocks and funds."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        result = KnowledgeGraphBuilder.theme_diffusion(graph, "消费", max_depth=2)

        assert len(result["industries"]) >= 1
        assert len(result["stocks"]) >= 1

        fund_codes = [f["fund_code"] for f in result["exposed_funds"]]
        assert "110011" in fund_codes
        for f in result["exposed_funds"]:
            assert f["overlap_pct"] > 0


class TestCrossFundOverlap:
    """Tests for KnowledgeGraphBuilder.cross_fund_overlap()."""

    @pytest.fixture
    def two_fund_graph(self):
        """Build a graph with two funds sharing stock 600519."""
        kg = KnowledgeGraphBuilder()
        fund_a = {
            "code": "110011",
            "name": "易方达中小盘",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
                {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 30.5}],
        }
        fund_b = {
            "code": "006123",
            "name": "另一只基金",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 8.0},
                {"stock_code": "002415", "stock_name": "海康威视", "weight": 5.0},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 20.0}],
        }
        # Build a merged graph by building both subgraphs and combining
        graph = kg.build_from_holdings(fund_a)
        graph_b = kg.build_from_holdings(fund_b)
        graph.add_nodes_from(graph_b.nodes(data=True))
        graph.add_edges_from(graph_b.edges(data=True))
        # Merge graph attributes
        for k, v in graph_b.graph.items():
            if k not in graph.graph:
                graph.graph[k] = v
        return graph

    @pytest.fixture
    def three_fund_graph(self):
        """Build a graph with three funds with complex overlap patterns.

        Fund A: {600519, 000858, 300750}
        Fund B: {600519, 002415, 300750}
        Fund C: {600519, 601318, 002415}
        Shared: 600519 (all 3), 300750 (A+B), 002415 (B+C)
        """
        kg = KnowledgeGraphBuilder()
        fund_a = {
            "code": "110011",
            "name": "易方达中小盘",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.0},
                {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.0},
                {"stock_code": "300750", "stock_name": "宁德时代", "weight": 5.0},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        fund_b = {
            "code": "006123",
            "name": "新能源基金",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 8.0},
                {"stock_code": "002415", "stock_name": "海康威视", "weight": 6.0},
                {"stock_code": "300750", "stock_name": "宁德时代", "weight": 4.0},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 20.0}],
        }
        fund_c = {
            "code": "007777",
            "name": "稳健增长基金",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 7.0},
                {"stock_code": "601318", "stock_name": "中国平安", "weight": 5.0},
                {"stock_code": "002415", "stock_name": "海康威视", "weight": 3.0},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 15.0}],
        }
        graph = kg.build_from_holdings(fund_a)
        for fd in [fund_b, fund_c]:
            g = kg.build_from_holdings(fd)
            graph = nx.compose(graph, g)
        return graph

    @pytest.fixture
    def disjoint_fund_graph(self):
        """Build a graph with two funds that have no shared stocks."""
        kg = KnowledgeGraphBuilder()
        fund_a = {
            "code": "110011",
            "name": "易方达中小盘",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
                {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 30.5}],
        }
        fund_c = {
            "code": "007777",
            "name": "不重叠基金",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "300999", "stock_name": "金龙鱼", "weight": 6.0},
                {"stock_code": "002415", "stock_name": "海康威视", "weight": 5.0},
            ],
            "sectors": [{"industry": "食品饮料", "weight": 15.0}],
        }
        graph = kg.build_from_holdings(fund_a)
        graph_c = kg.build_from_holdings(fund_c)
        graph.add_nodes_from(graph_c.nodes(data=True))
        graph.add_edges_from(graph_c.edges(data=True))
        return graph

    def test_cross_fund_overlap_shared_stocks(self, two_fund_graph):
        """Two funds that both hold 600519."""
        result = KnowledgeGraphBuilder.cross_fund_overlap(two_fund_graph, ["110011", "006123"])

        # Should find 600519 as shared
        assert len(result["shared_stocks"]) >= 1
        stock_codes = [s["stock_code"] for s in result["shared_stocks"]]
        assert "600519" in stock_codes

        maotai = next(s for s in result["shared_stocks"] if s["stock_code"] == "600519")
        assert "110011" in maotai["held_by"]
        assert "006123" in maotai["held_by"]
        # total_weight_pct = 9.5 + 8.0 = 17.5
        assert maotai["total_weight_pct"] == pytest.approx(17.5, rel=0.01)

        # Overlap matrix
        matrix = result["overlap_matrix"]
        assert "110011" in matrix
        assert "006123" in matrix
        # 110011 has {600519, 000858}, 006123 has {600519, 002415}
        # overlap 110011 → 006123: 1/2 = 50%
        assert matrix["110011"]["006123"] == pytest.approx(50.0, rel=0.01)
        # overlap 006123 → 110011: 1/2 = 50%
        assert matrix["006123"]["110011"] == pytest.approx(50.0, rel=0.01)
        # Self overlap is 100%
        assert matrix["110011"]["110011"] == 100.0
        assert matrix["006123"]["006123"] == 100.0

    def test_cross_fund_overlap_three_funds(self, three_fund_graph):
        """3+ funds with complex overlap: shared stocks across subsets."""
        result = KnowledgeGraphBuilder.cross_fund_overlap(
            three_fund_graph, ["110011", "006123", "007777"]
        )

        # 600519 is held by all 3
        shared_codes = [s["stock_code"] for s in result["shared_stocks"]]
        assert "600519" in shared_codes
        maotai = next(s for s in result["shared_stocks"] if s["stock_code"] == "600519")
        assert len(maotai["held_by"]) == 3
        assert set(maotai["held_by"]) == {"110011", "006123", "007777"}
        assert maotai["total_weight_pct"] == pytest.approx(24.0, rel=0.01)

        # 300750 is held by A+B
        # 002415 is held by B+C
        assert "300750" in shared_codes
        assert "002415" in shared_codes
        nd = next(s for s in result["shared_stocks"] if s["stock_code"] == "300750")
        assert set(nd["held_by"]) == {"110011", "006123"}
        hik = next(s for s in result["shared_stocks"] if s["stock_code"] == "002415")
        assert set(hik["held_by"]) == {"006123", "007777"}

        # Overlap matrix
        matrix = result["overlap_matrix"]
        # A = {600519, 000858, 300750}, B = {600519, 002415, 300750}
        # A ∩ B = {600519, 300750} → 2/3 ≈ 66.67%
        assert matrix["110011"]["006123"] == pytest.approx(66.67, rel=0.01)
        # B ∩ A = {600519, 300750} → 2/3 ≈ 66.67%
        assert matrix["006123"]["110011"] == pytest.approx(66.67, rel=0.01)
        # A ∩ C = {600519} → 1/3 ≈ 33.33%
        assert matrix["110011"]["007777"] == pytest.approx(33.33, rel=0.01)
        # C ∩ A = {600519} → 1/3 ≈ 33.33%
        assert matrix["007777"]["110011"] == pytest.approx(33.33, rel=0.01)
        # B ∩ C = {600519, 002415} → 2/3 ≈ 66.67%
        assert matrix["006123"]["007777"] == pytest.approx(66.67, rel=0.01)
        # C ∩ B = {600519, 002415} → 2/3 ≈ 66.67%
        assert matrix["007777"]["006123"] == pytest.approx(66.67, rel=0.01)
        # Self overlaps
        assert matrix["110011"]["110011"] == 100.0
        assert matrix["006123"]["006123"] == 100.0
        assert matrix["007777"]["007777"] == 100.0

    def test_cross_fund_overlap_no_shared(self, disjoint_fund_graph):
        """Two funds with disjoint holdings → empty shared_stocks."""
        result = KnowledgeGraphBuilder.cross_fund_overlap(
            disjoint_fund_graph, ["110011", "007777"]
        )

        assert result["shared_stocks"] == []

        matrix = result["overlap_matrix"]
        assert matrix["110011"]["007777"] == 0.0
        assert matrix["007777"]["110011"] == 0.0

    def test_cross_fund_overlap_single_fund(self, two_fund_graph):
        """Single fund list returns no shared stocks (need 2+)."""
        result = KnowledgeGraphBuilder.cross_fund_overlap(two_fund_graph, ["110011"])
        assert result["shared_stocks"] == []
        assert "110011" in result["overlap_matrix"]
        assert result["overlap_matrix"]["110011"]["110011"] == 100.0

    def test_cross_fund_overlap_nonexistent_fund(self, two_fund_graph):
        """Non-existent fund code handled gracefully."""
        result = KnowledgeGraphBuilder.cross_fund_overlap(
            two_fund_graph, ["110011", "FAKE000"]
        )
        # FAKE000 has no holdings, 110011 still has its stocks
        matrix = result["overlap_matrix"]
        assert matrix["110011"]["FAKE000"] == 0.0
        assert matrix["FAKE000"]["110011"] == 0.0
        assert matrix["FAKE000"]["FAKE000"] == 100.0


class TestKnowledgeGraphRefresh:
    """Tests for KnowledgeGraphBuilder.refresh() incremental update."""

    @pytest.fixture
    def builder(self):
        return KnowledgeGraphBuilder()

    @pytest.fixture
    def fund_a_data(self):
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

    @pytest.fixture
    def fund_b_data(self):
        return {
            "code": "006123",
            "name": "某新能源基金",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "300750", "stock_name": "宁德时代", "weight": 8.0},
            ],
            "sectors": [
                {"industry": "电力设备", "weight": 25.0},
            ],
        }

    @pytest.fixture
    def single_fund_graph(self, builder, fund_a_data):
        return builder.build_from_holdings(fund_a_data)

    def test_refresh_add_new_fund(self, builder, single_fund_graph, fund_b_data):
        """Refresh adds a new fund that wasn't in the graph before."""
        refreshed = KnowledgeGraphBuilder.refresh(
            single_fund_graph,
            [fund_b_data],
        )
        # Both fund nodes should exist
        assert refreshed.has_node("fund:110011")
        assert refreshed.has_node("fund:006123")

        # New fund's stock and industry should be present
        assert refreshed.has_node("stock:300750")
        assert refreshed.has_node("industry:sw_电力设备")

        # Old fund's data should be intact
        old_stock = "stock:600519"
        assert refreshed.has_node(old_stock)
        assert refreshed.has_node("industry:sw_食品饮料")

        # Version should have incremented
        assert refreshed.graph.get("version", 0) >= 1

    def test_refresh_remove_stale_holding(self, builder, single_fund_graph, fund_a_data):
        """Refresh removes a holding that's no longer in the fund data."""
        # Remove one holding (601318) and change another's weight
        updated_fund_a = dict(fund_a_data)
        updated_fund_a["holdings"] = [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 10.0},  # weight changed
            # 000858 removed
            # 601318 removed
        ]

        refreshed = KnowledgeGraphBuilder.refresh(
            single_fund_graph,
            [updated_fund_a],
        )

        # Stock no longer held should have HOLDS edge removed
        fund_id = "fund:110011"
        # 600519 still held
        assert refreshed.has_edge(fund_id, "stock:600519")
        # 000858 and 601318 should no longer have HOLDS edges
        assert not refreshed.has_edge(fund_id, "stock:000858")
        assert not refreshed.has_edge(fund_id, "stock:601318")

        # Stale stock nodes should be removed (orphaned)
        assert not refreshed.has_node("stock:000858")
        assert not refreshed.has_node("stock:601318")

    def test_refresh_all_funds_changed(self, builder, fund_a_data):
        """Completely replace all holdings for a fund."""
        initial = builder.build_from_holdings(fund_a_data)

        # Replace with entirely different holdings
        changed_fund = dict(fund_a_data)
        changed_fund["holdings"] = [
            {"stock_code": "300750", "stock_name": "宁德时代", "weight": 8.0},
            {"stock_code": "002415", "stock_name": "海康威视", "weight": 6.0},
        ]
        changed_fund["sectors"] = [
            {"industry": "电力设备", "weight": 20.0},
        ]

        refreshed = KnowledgeGraphBuilder.refresh(initial, [changed_fund])

        fund_id = "fund:110011"
        # Old holdings should be gone
        assert not refreshed.has_edge(fund_id, "stock:600519")
        assert not refreshed.has_edge(fund_id, "stock:000858")
        assert not refreshed.has_edge(fund_id, "stock:601318")
        # Old stock nodes should be gone (orphaned)
        assert not refreshed.has_node("stock:600519")
        assert not refreshed.has_node("stock:000858")
        assert not refreshed.has_node("stock:601318")
        # New holdings should be present
        assert refreshed.has_edge(fund_id, "stock:300750")
        assert refreshed.has_edge(fund_id, "stock:002415")
        # Old industry should be gone
        assert not refreshed.has_edge(fund_id, "industry:sw_食品饮料")
        assert not refreshed.has_edge(fund_id, "industry:sw_金融")
        # New industry should be present
        assert refreshed.has_edge(fund_id, "industry:sw_电力设备")
        # Version bumped
        assert refreshed.graph.get("version", 0) >= 1

    def test_refresh_no_changes(self, builder, fund_a_data):
        """Refresh with identical fund data produces an equivalent graph."""
        graph = builder.build_from_holdings(fund_a_data)
        # Capture original state before version bump
        graph.graph["version"] = 0

        refreshed = KnowledgeGraphBuilder.refresh(graph, [fund_a_data])

        fund_id = "fund:110011"
        # Same nodes should exist
        assert refreshed.has_node(fund_id)
        assert refreshed.has_node("stock:600519")
        assert refreshed.has_node("stock:000858")
        assert refreshed.has_node("stock:601318")
        assert refreshed.has_node("industry:sw_食品饮料")
        assert refreshed.has_node("industry:sw_金融")
        # Same edges
        assert refreshed.has_edge(fund_id, "stock:600519")
        assert refreshed.has_edge(fund_id, "stock:000858")
        assert refreshed.has_edge(fund_id, "stock:601318")
        assert refreshed.has_edge(fund_id, "industry:sw_食品饮料")
        assert refreshed.has_edge(fund_id, "industry:sw_金融")
        # Weights unchanged
        assert refreshed.get_edge_data(fund_id, "stock:600519")["edge_data"].weight == pytest.approx(9.5)
        # Version bumped
        assert refreshed.graph.get("version", 0) >= 1

    def test_refresh_preserves_events(self, builder, sample_fund_data):
        """Existing event nodes survive a refresh."""
        graph = builder.build_from_holdings(sample_fund_data)

        # Add an event
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
        graph.add_node(event.id, data=event)
        impact_edge = KGEdge(
            source=event.id,
            target="stock:600519",
            edge_type=KGEdgeType.IMPACTS,
            polarity=0.8,
            magnitude=0.6,
        )
        graph.add_edge(event.id, "stock:600519", edge_data=impact_edge)

        # Refresh with same fund data
        refreshed = KnowledgeGraphBuilder.refresh(
            graph,
            [sample_fund_data],
        )

        # Event node must survive
        assert refreshed.has_node("event:evt_001")
        assert refreshed.nodes["event:evt_001"]["data"].event_type == "earnings_surprise"

        # Impact edge must survive
        assert refreshed.has_edge("event:evt_001", "stock:600519")

    def test_refresh_shared_stock_across_funds(self, builder, fund_a_data, fund_b_data):
        """If a stock is held by multiple funds, removing it from one keeps it."""
        # Fund B initially holds 600519 too
        fund_b_with_shared = dict(fund_b_data)
        fund_b_with_shared["holdings"] = [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 5.0},
            {"stock_code": "300750", "stock_name": "宁德时代", "weight": 8.0},
        ]

        # Build joint graph
        graph_a = builder.build_from_holdings(fund_a_data)
        graph_b = builder.build_from_holdings(fund_b_with_shared)
        combined = nx.compose(graph_a, graph_b)
        combined.graph["version"] = 0

        # Now remove 600519 from fund A
        updated_fund_a = dict(fund_a_data)
        updated_fund_a["holdings"] = [
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            {"stock_code": "601318", "stock_name": "中国平安", "weight": 5.1},
        ]

        refreshed = KnowledgeGraphBuilder.refresh(
            combined,
            [updated_fund_a, fund_b_with_shared],
        )

        # Stock 600519 still exists (Fund B still holds it)
        assert refreshed.has_node("stock:600519")
        # But no longer has HOLDS edge from fund A
        assert not refreshed.has_edge("fund:110011", "stock:600519")
        # Still has HOLDS edge from fund B
        assert refreshed.has_edge("fund:006123", "stock:600519")


class TestKnowledgeGraphDiff:
    """Tests for KnowledgeGraphBuilder.diff() structural comparison."""

    @pytest.fixture
    def builder(self):
        return KnowledgeGraphBuilder()

    @pytest.fixture
    def fund_a_data(self):
        return {
            "code": "110011",
            "name": "易方达中小盘混合",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
                {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 30.5},
            ],
        }

    def test_diff_identical_graphs(self, builder, fund_a_data):
        """Diff of a graph against itself should be empty."""
        graph = builder.build_from_holdings(fund_a_data)
        diff = KnowledgeGraphBuilder.diff(graph, graph)
        assert diff.is_empty()
        assert diff.summary() == "no changes"

    def test_diff_added_removed(self, builder, fund_a_data):
        """Diff correctly identifies added and removed nodes/edges."""
        graph_a = builder.build_from_holdings(fund_a_data)

        # Create a second graph with an additional fund
        fund_b_data = {
            "code": "006123",
            "name": "某新能源基金",
            "fund_type": "equity",
            "holdings": [
                {"stock_code": "300750", "stock_name": "宁德时代", "weight": 8.0},
            ],
            "sectors": [
                {"industry": "电力设备", "weight": 25.0},
            ],
        }
        graph_b = builder.build_from_holdings(fund_b_data)
        combined = nx.compose(graph_a, graph_b)
        combined.graph["version"] = 0

        diff = KnowledgeGraphBuilder.diff(graph_a, combined)

        # Should have added nodes (fund B + B's stock + B's industry + B's themes)
        assert "fund:006123" in diff.added_nodes
        assert "stock:300750" in diff.added_nodes
        assert "industry:sw_电力设备" in diff.added_nodes

        # Should have added edges
        assert len(diff.added_edges) > 0

        # No nodes or edges removed
        assert len(diff.removed_nodes) == 0
        assert len(diff.removed_edges) == 0

    def test_diff_removed_nodes(self, builder, fund_a_data):
        """Diff correctly identifies removed nodes."""
        graph_a = builder.build_from_holdings(fund_a_data)
        graph_a.graph["version"] = 0

        # Remove a stock node manually
        graph_b = graph_a.copy()
        graph_b.remove_node("stock:000858")

        diff = KnowledgeGraphBuilder.diff(graph_a, graph_b)
        assert "stock:000858" in diff.removed_nodes
        assert len(diff.added_nodes) == 0

    def test_diff_modified_nodes(self, builder, fund_a_data):
        """Diff detects nodes with changed data."""
        graph_a = builder.build_from_holdings(fund_a_data)
        graph_a.graph["version"] = 0

        # Create modified version with changed stock weight (edge data change)
        graph_b = graph_a.copy()

        # Change a stock node's data
        stock_id = "stock:600519"
        from src.graph.schema import StockNode
        old_node = graph_b.nodes[stock_id]["data"]
        modified_stock = StockNode(
            code=old_node.code,
            name="贵州茅台(modified)",
            sector=old_node.sector,
            industry=old_node.industry,
        )
        graph_b.nodes[stock_id]["data"] = modified_stock

        diff = KnowledgeGraphBuilder.diff(graph_a, graph_b)

        assert stock_id in diff.modified_nodes


class TestKnowledgeGraphEdgeCoverage:
    """Targeted tests for remaining coverage gaps in graph.py."""

    @pytest.fixture
    def builder(self):
        return KnowledgeGraphBuilder()

    def test_refresh_empty_industry_name(self, builder):
        """Refresh with empty industry name hits the continue guard in _update_fund_holdings."""
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = builder.build_from_holdings(fund_data)

        # Refresh with an empty industry in sectors
        changed = dict(fund_data)
        changed["sectors"] = [
            {"industry": "", "weight": 0.0},
            {"industry": "食品饮料", "weight": 30.0},
        ]
        refreshed = KnowledgeGraphBuilder.refresh(graph, [changed])
        assert refreshed.has_node("fund:110011")
        assert refreshed.has_node("stock:600519")

    def test_refresh_update_with_explicit_stock_industry(self, builder):
        """Refresh where holdings have explicit industry sets BELONGS_TO edges."""
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = builder.build_from_holdings(fund_data)

        # Refresh with explicit industry on the holding
        changed = dict(fund_data)
        changed["holdings"] = [
            {"stock_code": "600519", "stock_name": "茅台", "weight": 6.0, "industry": "食品饮料"},
        ]
        refreshed = KnowledgeGraphBuilder.refresh(graph, [changed])

        stock_id = "stock:600519"
        industry_id = "industry:sw_食品饮料"
        assert refreshed.has_edge(stock_id, industry_id)
        edge_data = refreshed.get_edge_data(stock_id, industry_id)
        edge = edge_data.get("edge_data")
        assert edge is not None
        assert edge.edge_type == KGEdgeType.BELONGS_TO

    def test_refresh_removes_stale_exposes_edge(self, builder):
        """Refresh removes EXPOSES edges for sectors that are no longer present."""
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [
                {"industry": "食品饮料", "weight": 25.0},
                {"industry": "金融", "weight": 10.0},
            ],
        }
        graph = builder.build_from_holdings(fund_data)
        assert graph.has_edge("fund:110011", "industry:sw_金融")

        # Remove 金融 from sectors
        changed = dict(fund_data)
        changed["sectors"] = [{"industry": "食品饮料", "weight": 30.0}]
        refreshed = KnowledgeGraphBuilder.refresh(graph, [changed])

        assert refreshed.has_edge("fund:110011", "industry:sw_食品饮料")
        assert not refreshed.has_edge("fund:110011", "industry:sw_金融")

    def test_get_impact_chain_through_industry(self, builder, sample_fund_data):
        """Event that impacts an industry node propagates to fund via EXPOSES."""
        graph = builder.build_from_holdings(sample_fund_data)

        # Create an event that impacts an industry directly
        event = EventNode(
            event_id="evt_002",
            event_type="regulatory",
            subtype="policy_change",
            date="2026-05-28",
            polarity=-0.5,
            magnitude=0.7,
            time_horizon="long",
            description="白酒行业消费税调整"
        )
        graph.add_node(event.id, data=event)

        industry_id = "industry:sw_食品饮料"
        impact_edge = KGEdge(
            source=event.id,
            target=industry_id,
            edge_type=KGEdgeType.IMPACTS,
            polarity=-0.5,
            magnitude=0.7,
        )
        graph.add_edge(event.id, industry_id, edge_data=impact_edge)

        impact = KnowledgeGraphBuilder().get_impact_chain(graph, "evt_002", "110011")

        assert len(impact["paths"]) >= 1
        # At least one path should involve the industry
        industry_paths = [p for p in impact["paths"] if "industry" in p]
        assert len(industry_paths) >= 1
        assert impact["total_polarity"] != 0.0
        assert impact["total_magnitude"] != 0.0


class TestRemainingCoverageGaps:
    """Tests for the last uncovered defensive branches."""

    def test_query_relevance_keyword_only_match(self):
        """News with theme keyword (not exact theme name) yields partial theme_hit."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # "白酒" is a keyword for a theme linked to 食品饮料, without using exact theme name
        news = {"title": "某基金重仓白酒板块持续走强", "entities": []}
        relevance = kg.query_relevance(graph, "110011", news)
        assert relevance > 0.0

    def test_get_fund_exposure_with_non_exposes_edge(self):
        """get_fund_exposure handles edges that are not EXPOSES type on the fund."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # Add a non-EXPOSES edge from fund (e.g. a CORRELATES_WITH edge)
        from src.graph.schema import KGEdge
        extra_edge = KGEdge(
            source="fund:110011",
            target="fund:999999",
            edge_type=KGEdgeType.CORRELATES_WITH,
        )
        graph.add_node("fund:999999", data=FundNode(code="999999", name="other"))
        graph.add_edge("fund:110011", "fund:999999", edge_data=extra_edge)

        exposure = kg.get_fund_exposure(graph, "110011")
        # Should still work fine despite the non-EXPOSES edge
        assert "industries" in exposure
        assert "themes" in exposure
        assert len(exposure["industries"]) >= 1

    def test_entity_chain_handles_non_belongs_to_edge(self):
        """Entity chain tolerates non-BELONGS_TO edges from stock nodes."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # Add a non-BELONGS_TO edge from a stock (e.g. CORRELATES_WITH to another stock)
        extra = KGEdge(
            source="stock:600519",
            target="stock:000858",
            edge_type=KGEdgeType.CORRELATES_WITH,
        )
        graph.add_node("stock:000858", data=StockNode(code="000858", name="五粮液"))
        graph.add_edge("stock:600519", "stock:000858", edge_data=extra)

        result = KnowledgeGraphBuilder.entity_chain(graph, "110011")
        assert len(result["holdings"]) >= 1
        # Should have progressed past the non-BELONGS_TO edge
        assert result["holdings"][0]["industry"] != {}

    def test_entity_chain_handles_non_theme_edge(self):
        """Entity chain tolerates non-IN_THEME edges from industry nodes."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # Add a non-IN_THEME edge from industry
        extra = KGEdge(
            source="industry:sw_食品饮料",
            target="industry:sw_金融",
            edge_type=KGEdgeType.CORRELATES_WITH,
        )
        graph.add_node("industry:sw_金融", data=IndustryNode(code="sw_金融", name="金融"))
        graph.add_edge("industry:sw_食品饮料", "industry:sw_金融", edge_data=extra)

        result = KnowledgeGraphBuilder.entity_chain(graph, "110011")
        assert len(result["holdings"]) >= 1
        assert len(result["holdings"][0]["themes"]) >= 1

    def test_theme_diffusion_skips_non_belongs_to_edges(self, sample_fund_data):
        """Theme diffusion's in_edges loop skips non-BELONGS_TO edges."""
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Add a non-BELONGS_TO edge from industry 食品饮料 to a stock
        extra = KGEdge(
            source="industry:sw_食品饮料",
            target="stock:999999",
            edge_type=KGEdgeType.CORRELATES_WITH,
        )
        graph.add_node("stock:999999", data=StockNode(code="999999", name="dummy"))
        graph.add_edge("industry:sw_食品饮料", "stock:999999", edge_data=extra)

        result = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒", max_depth=2)
        # Should still work and find the real stocks
        assert len(result["stocks"]) >= 1
        stock_codes = [s["stock_code"] for s in result["stocks"]]
        assert "600519" in stock_codes or "000858" in stock_codes

    def test_refresh_edge_without_edge_data(self):
        """Refresh handles fund out-edges that lack edge_data attribute."""
        kg = KnowledgeGraphBuilder()
        fund_a_data = {
            "code": "110011",
            "name": "易方达中小盘混合",
            "fund_type": "hybrid",
            "holdings": [
                {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            ],
            "sectors": [
                {"industry": "食品饮料", "weight": 30.5},
            ],
        }
        graph = kg.build_from_holdings(fund_a_data)
        # Manually add an edge without edge_data to the fund
        graph.add_edge("fund:110011", "macro:test", data={})
        graph.add_node("macro:test", data=MacroFactorNode(name="test", factor_type="test"))

        # Refresh should not crash when encountering this edge
        refreshed = KnowledgeGraphBuilder.refresh(graph, [fund_a_data])
        assert refreshed.has_node("fund:110011")


class TestFinalCoverageGaps:
    """Ultra-targeted tests for the last uncovered lines in graph.py."""

    def test_query_relevance_industry_hit_exact_match(self):
        """News title containing exact industry name triggers industry_hit=1.0 branch."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # "食品饮料" is the industry name - should trigger industry_hit=1.0 (lines 841-842)
        news = {"title": "食品饮料板块业绩稳健增长", "entities": []}
        relevance = kg.query_relevance(graph, "110011", news)
        assert relevance > 0.0

    def test_get_fund_exposure_edge_without_data(self):
        """Edge without edge_data attribute triggers continue on line 887."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # Add an edge from fund without edge_data attribute
        graph.add_edge("fund:110011", "fund:999999")
        graph.add_node("fund:999999", data=FundNode(code="999999", name="other"))

        exposure = kg.get_fund_exposure(graph, "110011")
        assert "industries" in exposure
        assert len(exposure["industries"]) >= 1

    def test_theme_diffusion_skips_non_holds_reverse_edge(self):
        """In_edges of stock with non-HOLDS edge type triggers line 658 guard."""
        kg = KnowledgeGraphBuilder()
        fund_data = {
            "code": "110011",
            "name": "test",
            "fund_type": "hybrid",
            "holdings": [{"stock_code": "600519", "stock_name": "茅台", "weight": 5.0}],
            "sectors": [{"industry": "食品饮料", "weight": 25.0}],
        }
        graph = kg.build_from_holdings(fund_data)
        # Add another fund with a non-HOLDS edge to the same stock
        # This way the HOLDS edge from 110011 is preserved and we also have a non-HOLDS edge
        graph.add_node("fund:999999", data=FundNode(code="999999", name="other"))
        corr_edge = KGEdge(
            source="fund:999999",
            target="stock:600519",
            edge_type=KGEdgeType.CORRELATES_WITH,
        )
        graph.add_edge("fund:999999", "stock:600519", edge_data=corr_edge)

        result = KnowledgeGraphBuilder.theme_diffusion(graph, "白酒", max_depth=2)
        # Should still find the fund via the HOLDS edge (not the CORRELATES_WITH one)
        assert len(result["exposed_funds"]) >= 1
        fund_codes = [f["fund_code"] for f in result["exposed_funds"]]
        assert "110011" in fund_codes
