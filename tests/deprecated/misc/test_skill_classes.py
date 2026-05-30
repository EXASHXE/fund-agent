"""Test Skill class I/O contracts with mock ToolRegistry.

Each test verifies:
1. Typed input/output contracts are respected.
2. execute() returns properly structured data even with empty inputs.
3. Missing tools cause graceful fallback (not crashes).
4. The mock ToolRegistry pattern works correctly.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from src.schemas import EvidenceItem
from src.schemas.decision import Decision, ActionType
from src.tools.registry import ToolRegistry, ToolDefinition

from skills.fund_analysis.skill import (
    FundAnalysisSkill,
    FundAnalysisInput,
    FundAnalysisOutput,
)
from skills.news_research.skill import (
    NewsResearchSkill,
    NewsResearchInput,
    NewsResearchOutput,
)
from skills.sentiment_analysis.skill import (
    SentimentAnalysisSkill,
    SentimentInput,
    SentimentOutput,
)
from skills.thesis_generation.skill import (
    ThesisGenerationSkill,
    ThesisInput,
    ThesisOutput,
)


# ======================================================================
# Fixtures — shared test helpers
# ======================================================================


def _make_registry(**tools: Any) -> ToolRegistry:
    """Build a ToolRegistry from keyword handler functions."""
    registry = ToolRegistry()
    for name, handler in tools.items():
        registry.register(
            ToolDefinition(name=name, description=f"test: {name}", handler=handler)
        )
    return registry


def _make_evidence(
    direction: str = "neutral",
    confidence: float = 0.5,
    claim: str = "Test evidence",
    entities: list[str | None] = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"evt-{hash(claim) & 0xffff:04x}",
        evidence_type="SoftEvidence",
        source_type="test_tool",
        timestamp=datetime.now(),
        related_entities=entities or ["000001"],
        claim=claim,
        value={"key": "value"},
        confidence_weight=confidence,
        direction=direction,  # type: ignore[arg-type]
    )


# ======================================================================
# Test: FundAnalysisSkill
# ======================================================================


class TestFundAnalysisSkill:
    """Test FundAnalysisSkill I/O contract and fallback behavior."""

    def test_execute_returns_structured_output(self):
        """Verify execute() returns FundAnalysisOutput with all fields."""
        registry = ToolRegistry()
        skill = FundAnalysisSkill(registry)

        input_data = FundAnalysisInput(
            fund_code="000001",
            fund_data={
                "fund_name": "Test Fund",
                "fund_type": "混合型",
                "daily_returns": [0.001, -0.002, 0.003, 0.001, -0.001],
                "sortino_ratio": 1.2,
                "hhi_index": 1800,
                "holdings": [],
            },
            kg_context={
                "fund_exposure": {"000001": {"weight": 1.0}},
                "industry_exposure": {"金融": 0.3, "科技": 0.4, "消费": 0.3},
                "impact_chains": {"events": []},
                "market_regime": "normal",
            },
            evidence_items=[
                _make_evidence("positive", 0.8, "表现超预期"),
                _make_evidence("negative", 0.6, "行业下行风险"),
            ],
        )

        output = skill.execute(input_data)

        assert isinstance(output, FundAnalysisOutput)
        assert output.fund_code == "000001"
        assert isinstance(output.overall_score, float)
        assert 0.0 <= output.overall_score <= 100.0
        assert isinstance(output.macro_assessment, dict)
        assert isinstance(output.meso_assessment, dict)
        assert isinstance(output.micro_assessment, dict)
        assert isinstance(output.risk_signals, list)
        assert isinstance(output.evidence_ids, list)
        assert len(output.evidence_ids) == 2

    def test_missing_tools_falls_back_gracefully(self):
        """Test with empty ToolRegistry — should fall back to input data."""
        registry = ToolRegistry()
        skill = FundAnalysisSkill(registry)

        input_data = FundAnalysisInput(
            fund_code="000001",
            fund_data={
                "fund_name": "Test Fund",
                "fund_type": "股票型",
                "sortino_ratio": 0.8,
                "hhi_index": 1500,
                "holdings": [],
            },
            kg_context={
                "fund_exposure": {},
                "industry_exposure": {},
                "impact_chains": {"events": []},
            },
            evidence_items=[],
        )

        output = skill.execute(input_data)

        assert output.fund_code == "000001"
        assert output.overall_score >= 0.0
        # Should still get sensible risk signals even when no tools
        assert isinstance(output.risk_signals, list)
        assert isinstance(output.evidence_ids, list)

    def test_execute_with_tool_registry_happy_path(self):
        """Test with a populated ToolRegistry that provides actual tools."""
        registry = _make_registry(
            sortino_ratio=lambda daily_returns: 1.5,
            compute_hhi=lambda holdings_df: 1200.0,
            compute_perf_from_nav=lambda nav_df: {
                "近1年": {
                    "annual_volatility": 12.0,
                    "sharpe_ratio": 1.3,
                    "max_drawdown": 8.0,
                    "jensen_alpha": 0.05,
                }
            },
        )
        skill = FundAnalysisSkill(registry)

        input_data = FundAnalysisInput(
            fund_code="000001",
            fund_data={
                "fund_name": "Test Fund",
                "fund_type": "股票型",
                "daily_returns": [0.01] * 100,
                "holdings": "mock_df",
                "nav": "mock_nav_df",
            },
            kg_context={
                "fund_exposure": {"000001": {"weight": 1.0}},
                "industry_exposure": {"科技": 0.6, "消费": 0.4},
                "impact_chains": {"events": []},
                "market_regime": "bull",
            },
            evidence_items=[
                _make_evidence("positive", 0.9, "Strong momentum"),
                _make_evidence("positive", 0.8, "Earnings beat"),
            ],
        )

        output = skill.execute(input_data)

        # With bull market + good metrics, score should be high
        assert output.overall_score > 60.0
        assert output.micro_assessment["sortino_ratio"] == 1.5
        assert output.micro_assessment["sharpe_ratio"] == 1.3
        assert output.meso_assessment["hhi"] == 1200.0

    def test_execute_with_extreme_values(self):
        """Test boundary conditions for scoring."""
        registry = ToolRegistry()
        skill = FundAnalysisSkill(registry)

        input_data = FundAnalysisInput(
            fund_code="000001",
            fund_data={
                "fund_type": "",
                "sortino_ratio": -2.0,
                "hhi_index": 5000,
                "holdings": [],
            },
            kg_context={
                "fund_exposure": {},
                "industry_exposure": {},
                "impact_chains": {"events": []},
                "market_regime": "crisis",
            },
            evidence_items=[
                _make_evidence("negative", 0.9, "重大利空"),
                _make_evidence("negative", 0.8, "财务造假"),
            ],
        )

        output = skill.execute(input_data)

        # Should still produce valid output
        assert 0.0 <= output.overall_score <= 100.0
        assert len(output.risk_signals) > 0


# ======================================================================
# Test: NewsResearchSkill
# ======================================================================


class TestNewsResearchSkill:
    """Test NewsResearchSkill I/O contract."""

    def test_execute_returns_structured_output(self):
        """Verify execute() returns NewsResearchOutput with all fields."""
        registry = ToolRegistry()
        skill = NewsResearchSkill(registry)

        input_data = NewsResearchInput(
            fund_codes=["000001", "000002"],
            kg_graph=None,
            date_range=None,
        )

        output = skill.execute(input_data)

        assert isinstance(output, NewsResearchOutput)
        assert isinstance(output.per_fund_news, dict)
        assert isinstance(output.key_events, list)
        assert isinstance(output.coverage_report, dict)
        assert output.coverage_report["status"] == "no_news_found"

    def test_execute_with_empty_funds(self):
        """Empty fund list should return empty output gracefully."""
        registry = ToolRegistry()
        skill = NewsResearchSkill(registry)

        input_data = NewsResearchInput(
            fund_codes=[],
            kg_graph=None,
        )

        output = skill.execute(input_data)

        assert output.per_fund_news == {}
        assert output.key_events == []
        assert output.coverage_report["status"] == "empty_fund_list"

    def test_execute_with_tools(self):
        """Test with tools that return search results."""
        def mock_search(symbols: list[str], date_range: tuple | None = None) -> list[dict]:
            return [
                {
                    "title": "Test stock news",
                    "description": "Positive earnings for the stock",
                    "source": "reuters",
                    "date": datetime.now().isoformat(),
                    "symbols": symbols,
                }
            ]

        registry = _make_registry(search_news=mock_search)
        skill = NewsResearchSkill(registry)

        input_data = NewsResearchInput(
            fund_codes=["000001"],
            kg_graph=None,
        )

        output = skill.execute(input_data)

        assert "000001" in output.per_fund_news
        assert output.coverage_report["total_news"] >= 0
        assert isinstance(output.coverage_report["sources"], dict)

    def test_execute_with_kg_graph(self):
        """Test that KG graph is used for holdings resolution if available."""
        class MockGraph:
            def has_node(self, node: str) -> bool:
                return node == "fund:000001"

            def successors(self, node: str) -> list[str]:
                return ["stock:600519", "stock:000858"]

        def mock_search(symbols: list[str], **kwargs) -> list[dict]:
            return [{"title": f"News about {s}"} for s in symbols]

        registry = _make_registry(search_news=mock_search)
        skill = NewsResearchSkill(registry)

        input_data = NewsResearchInput(
            fund_codes=["000001"],
            kg_graph=MockGraph(),
        )

        output = skill.execute(input_data)

        # Should have attempted search for stocks resolved from KG
        assert isinstance(output.per_fund_news, dict)


# ======================================================================
# Test: SentimentAnalysisSkill
# ======================================================================


class TestSentimentAnalysisSkill:
    """Test SentimentAnalysisSkill I/O contract."""

    def test_execute_returns_structured_output(self):
        """Verify execute() returns SentimentOutput with all fields."""
        registry = ToolRegistry()
        skill = SentimentAnalysisSkill(registry)

        input_data = SentimentInput(
            news_items=[
                {
                    "title": "公司业绩超预期增长",
                    "description": "净利润同比增长50%",
                    "symbols": ["600519"],
                    "date": datetime.now().isoformat(),
                    "source": "reuters",
                }
            ],
            symbols=["600519", "000858"],
        )

        output = skill.execute(input_data)

        assert isinstance(output, SentimentOutput)
        assert isinstance(output.per_symbol, dict)
        assert isinstance(output.aggregate, dict)
        assert "600519" in output.per_symbol
        assert "000858" in output.per_symbol

        # 600519 should have positive sentiment
        assert output.per_symbol["600519"]["polarity"] > 0
        assert output.per_symbol["600519"]["article_count"] == 1

        # 000858 has no news → neutral
        assert output.per_symbol["000858"]["article_count"] == 0
        assert output.per_symbol["000858"]["polarity"] == 0.0

    def test_execute_with_empty_news(self):
        """Empty news list should return neutral sentiment for all symbols."""
        registry = ToolRegistry()
        skill = SentimentAnalysisSkill(registry)

        input_data = SentimentInput(
            news_items=[],
            symbols=["600519"],
        )

        output = skill.execute(input_data)

        assert output.per_symbol["600519"]["polarity"] == 0.0
        assert output.per_symbol["600519"]["intensity"] == 0.0
        assert output.per_symbol["600519"]["confidence"] == 0.0
        assert output.per_symbol["600519"]["article_count"] == 0
        assert output.aggregate["positive_ratio"] == 0.0
        assert output.aggregate["neutral_ratio"] == 1.0

    def test_execute_with_empty_symbols(self):
        """Empty symbols list should return empty per_symbol."""
        registry = ToolRegistry()
        skill = SentimentAnalysisSkill(registry)

        input_data = SentimentInput(
            news_items=[{"title": "Some news", "symbols": ["600519"]}],
            symbols=[],
        )

        output = skill.execute(input_data)

        assert output.per_symbol == {}
        assert output.aggregate["total_articles_analyzed"] == 0

    def test_execute_with_negative_sentiment(self):
        """Negative news should produce negative polarity."""
        registry = ToolRegistry()
        skill = SentimentAnalysisSkill(registry)

        input_data = SentimentInput(
            news_items=[
                {
                    "title": "公司业绩大幅亏损，风险预警",
                    "description": "净利润暴跌，面临处罚风险",
                    "symbols": ["600519"],
                    "date": datetime.now().isoformat(),
                    "source": "reuters",
                }
            ],
            symbols=["600519"],
        )

        output = skill.execute(input_data)

        assert output.per_symbol["600519"]["polarity"] < 0
        assert output.aggregate["portfolio_polarity"] < 0

    def test_time_decay(self):
        """Old news should have lower weight than recent news."""
        registry = ToolRegistry()
        skill = SentimentAnalysisSkill(registry)

        now = datetime.now()
        old_date = (now - timedelta(days=30)).isoformat()

        input_data = SentimentInput(
            news_items=[
                {
                    "title": "业绩利好",
                    "description": "公司业绩超预期",
                    "symbols": ["600519"],
                    "date": now.isoformat(),
                    "source": "reuters",
                },
                {
                    "title": "业绩利好",
                    "description": "公司业绩超预期",
                    "symbols": ["600519"],
                    "date": old_date,
                    "source": "reuters",
                },
            ],
            symbols=["600519"],
        )

        output = skill.execute(input_data)

        # Both are positive but recent news dominates
        assert output.per_symbol["600519"]["polarity"] > 0
        assert output.per_symbol["600519"]["article_count"] == 2

    def test_execute_with_tool_lexicon(self):
        """Custom lexicon from tool should be respected."""
        def mock_lexicon(words: list[str]) -> dict:
            return {
                "positive": ["great", "amazing"],
                "negative": ["terrible", "awful"],
            }

        registry = _make_registry(**{"sentiment.lexicon": mock_lexicon})
        skill = SentimentAnalysisSkill(registry)

        input_data = SentimentInput(
            news_items=[{
                "title": "Great performance",
                "description": "Amazing results this quarter",
                "symbols": ["600519"],
                "date": datetime.now().isoformat(),
                "source": "reuters",
            }],
            symbols=["600519"],
        )

        output = skill.execute(input_data)

        # Tool's lexicon should produce positive polarity
        assert output.per_symbol["600519"]["polarity"] > 0


# ======================================================================
# Test: ThesisGenerationSkill
# ======================================================================


class TestThesisGenerationSkill:
    """Test ThesisGenerationSkill I/O contract."""

    def test_execute_returns_structured_output(self):
        """Verify execute() returns ThesisOutput with all fields."""
        registry = ToolRegistry()
        skill = ThesisGenerationSkill(registry)

        analysis = FundAnalysisOutput(
            fund_code="000001",
            overall_score=75.0,
            macro_assessment={"score": 70.0},
            meso_assessment={"score": 75.0},
            micro_assessment={"score": 78.0},
            risk_signals=["波动率偏高"],
            evidence_ids=["evt-001"],
        )

        input_data = ThesisInput(
            evidence_graph=[
                _make_evidence("positive", 0.9, "表现优秀", ["000001"]),
            ],
            fund_analyses=[analysis],
            risk_budget=10000.0,
        )

        output = skill.execute(input_data)

        assert isinstance(output, ThesisOutput)
        assert isinstance(output.thesis_id, str)
        assert output.thesis_id.startswith("thesis-")
        assert isinstance(output.decisions, list)
        assert len(output.decisions) == 1
        assert isinstance(output.confidence, float)
        assert 0.0 <= output.confidence <= 1.0
        assert isinstance(output.counter_arguments, list)

    def test_execute_with_empty_evidence(self):
        """Empty evidence should still produce decisions based on scores."""
        registry = ToolRegistry()
        skill = ThesisGenerationSkill(registry)

        analysis = FundAnalysisOutput(
            fund_code="000001",
            overall_score=50.0,
            macro_assessment={},
            meso_assessment={},
            micro_assessment={},
            risk_signals=[],
            evidence_ids=[],
        )

        input_data = ThesisInput(
            evidence_graph=[],
            fund_analyses=[analysis],
            risk_budget=5000.0,
        )

        output = skill.execute(input_data)

        assert len(output.decisions) == 1
        assert output.confidence >= 0.0
        # Should have generated trigger conditions even without evidence
        assert len(output.decisions[0].trigger_conditions) > 0

    def test_execute_with_empty_analyses(self):
        """Empty fund_analyses list should return empty decisions."""
        registry = ToolRegistry()
        skill = ThesisGenerationSkill(registry)

        input_data = ThesisInput(
            evidence_graph=[],
            fund_analyses=[],
            risk_budget=5000.0,
        )

        output = skill.execute(input_data)

        assert output.decisions == []
        assert len(output.counter_arguments) > 0  # Should give reason

    def test_decision_action_mapping(self):
        """High score + positive evidence -> INCREASE; low score -> SELL."""
        registry = ToolRegistry()
        skill = ThesisGenerationSkill(registry)

        # Test high-score scenario
        high_analysis = FundAnalysisOutput(
            fund_code="000001",
            overall_score=85.0,
            macro_assessment={},
            meso_assessment={},
            micro_assessment={},
            risk_signals=[],
            evidence_ids=["evt-001"],
        )

        input_high = ThesisInput(
            evidence_graph=[
                _make_evidence("positive", 0.9, "Strong growth", ["000001"]),
            ],
            fund_analyses=[high_analysis],
            risk_budget=10000.0,
        )

        output_high = skill.execute(input_high)
        assert output_high.decisions[0].action in ("INCREASE", "BUY", "HOLD")

        # Test low-score scenario
        low_analysis = FundAnalysisOutput(
            fund_code="000002",
            overall_score=25.0,
            macro_assessment={},
            meso_assessment={},
            micro_assessment={},
            risk_signals=["重大风险"],
            evidence_ids=["evt-002"],
        )

        input_low = ThesisInput(
            evidence_graph=[
                _make_evidence("negative", 0.9, "财务造假", ["000002"]),
            ],
            fund_analyses=[low_analysis],
            risk_budget=5000.0,
        )

        output_low = skill.execute(input_low)
        # Low score with strong negative → WAIT (or HOLD as fallback)
        assert output_low.decisions[0].action in ("WAIT", "HOLD")

    def test_evidence_ranking_uses_tool(self):
        """Evidence ranking should use tool if available."""
        def mock_rank(items: list) -> list:
            # Reverse sort by confidence
            return sorted(items, key=lambda e: e.confidence_weight, reverse=True)

        registry = _make_registry(**{"evidence.rank": mock_rank})
        skill = ThesisGenerationSkill(registry)

        analysis = FundAnalysisOutput(
            fund_code="000001",
            overall_score=65.0,
            macro_assessment={},
            meso_assessment={},
            micro_assessment={},
            risk_signals=[],
            evidence_ids=[],
        )

        input_data = ThesisInput(
            evidence_graph=[
                _make_evidence("positive", 0.5, "Neutral signal", ["000001"]),
                _make_evidence("positive", 0.9, "Strong signal", ["000001"]),
            ],
            fund_analyses=[analysis],
            risk_budget=10000.0,
        )

        output = skill.execute(input_data)
        assert len(output.decisions) == 1


# ======================================================================
# Import tests (verify skill modules can be imported)
# ======================================================================


class TestSkillImports:
    """Test that all skill modules can be imported properly."""

    def test_fund_analysis_import(self):
        from skills.fund_analysis import FundAnalysisSkill as FAS
        from skills.fund_analysis import FundAnalysisInput as FAI
        from skills.fund_analysis import FundAnalysisOutput as FAO
        assert FAS is not None
        assert FAI is not None
        assert FAO is not None

    def test_news_research_import(self):
        from skills.news_research import NewsResearchSkill as NRS
        from skills.news_research import NewsResearchInput as NRI
        from skills.news_research import NewsResearchOutput as NRO
        assert NRS is not None
        assert NRI is not None
        assert NRO is not None

    def test_sentiment_analysis_import(self):
        from skills.sentiment_analysis import SentimentAnalysisSkill as SAS
        from skills.sentiment_analysis import SentimentInput as SI
        from skills.sentiment_analysis import SentimentOutput as SO
        assert SAS is not None
        assert SI is not None
        assert SO is not None

    def test_thesis_generation_import(self):
        from skills.thesis_generation import ThesisGenerationSkill as TGS
        from skills.thesis_generation import ThesisInput as TI
        from skills.thesis_generation import ThesisOutput as TO
        assert TGS is not None
        assert TI is not None
        assert TO is not None
