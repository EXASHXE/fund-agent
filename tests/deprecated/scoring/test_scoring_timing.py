"""Test TimingScoreCalculator: timing/momentum scoring with regime awareness."""
import networkx as nx
import pytest

from legacy.analysis.scoring.types import ScoreComponent, MarketRegime


class TestTimingScoreCompute:
    """Core timing score computation."""

    def test_returns_score_component(self):
        """Should return a valid ScoreComponent."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        result = calc.compute({"code": "110011"}, MarketRegime.NORMAL, [])

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        assert isinstance(result.detail, dict)
        assert 0 <= result.confidence <= 1.0

    def test_trending_regime_highest_score(self):
        """Trending regime should give the highest timing score (good time to invest)."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        scores = {}
        for regime in MarketRegime:
            result = calc.compute({"code": "110011"}, regime, [])
            scores[regime] = result.score

        # TRENDING should be highest, CRISIS lowest
        assert scores[MarketRegime.TRENDING] >= scores[MarketRegime.NORMAL]
        assert scores[MarketRegime.CRISIS] < scores[MarketRegime.NORMAL]
        assert scores[MarketRegime.CRISIS] < scores[MarketRegime.HIGH_VOLATILITY]

    def test_crisis_regime_lowest_score(self):
        """Crisis regime should give the lowest timing score."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        result = calc.compute({"code": "110011"}, MarketRegime.CRISIS, [])
        assert result.score <= 40.0

    def test_positive_momentum_improves_score(self):
        """Positive momentum events should increase timing score."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        baseline = calc.compute({"code": "110011"}, MarketRegime.NORMAL, [])

        positive_events = [
            {"type": "earnings_surprise", "polarity": 0.8, "magnitude": 0.7},
            {"type": "fund_flow", "polarity": 0.6, "magnitude": 0.5},
        ]
        with_events = calc.compute({"code": "110011"}, MarketRegime.NORMAL, positive_events)

        assert with_events.score >= baseline.score

    def test_negative_momentum_worsens_score(self):
        """Negative momentum events should decrease timing score."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        baseline = calc.compute({"code": "110011"}, MarketRegime.NORMAL, [])

        negative_events = [
            {"type": "rate_change", "polarity": -0.7, "magnitude": 0.6},
            {"type": "earnings_miss", "polarity": -0.6, "magnitude": 0.7},
        ]
        with_events = calc.compute({"code": "110011"}, MarketRegime.NORMAL, negative_events)

        assert with_events.score <= baseline.score

    def test_detail_contains_regime(self):
        """Detail should include the detected regime."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        result = calc.compute({"code": "110011"}, MarketRegime.HIGH_VOLATILITY, [])
        assert result.detail.get("regime") == "high_volatility"

    def test_llm_client_acceptance(self):
        """Should accept llm_client parameter without error (stub)."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        result = calc.compute({"code": "110011"}, MarketRegime.NORMAL, [], llm_client=None)
        assert isinstance(result, ScoreComponent)

    def test_empty_fund_data_still_computable(self):
        """Empty/missing fund data should still return a valid score."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        result = calc.compute({}, MarketRegime.NORMAL, [])
        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100

    def test_all_regimes_have_valid_scores(self):
        """Every regime type should produce a valid score 0-100."""
        from legacy.analysis.scoring.timing import TimingScoreCalculator

        calc = TimingScoreCalculator()
        for regime in MarketRegime:
            result = calc.compute({"code": "110011"}, regime, [])
            assert 0 <= result.score <= 100, f"{regime} score={result.score}"
