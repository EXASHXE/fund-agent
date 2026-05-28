"""ScoreEngine: composite scoring orchestrator combining all 5 scoring dimensions."""
from __future__ import annotations

import networkx as nx

from src.analysis.scoring.quant import QuantScoreCalculator
from src.analysis.scoring.fundamental import FundamentalScoreCalculator
from src.analysis.scoring.event_score import EventScoreCalculator
from src.analysis.scoring.position import PositionScoreCalculator
from src.analysis.scoring.timing import TimingScoreCalculator
from src.analysis.scoring.regime import detect_regime
from src.analysis.scoring.factors import get_regime_weights
from src.analysis.scoring.types import ScoreComponent, MarketRegime, CompositeScore, score_level


class ScoreEngine:
    """Orchestrates all five scoring dimensions into a composite score.

    Pipeline:
    1. Detect market regime from NAV series and events
    2. Compute all 5 sub-scores (quant, fundamental, event, position, timing)
    3. Combine with regime-adaptive weights
    4. Convert to CompositeScore with level
    """

    def __init__(self, llm_client: object | None = None):
        self._llm_client = llm_client
        self.quant = QuantScoreCalculator()
        self.fundamental = FundamentalScoreCalculator()
        self.event_score = EventScoreCalculator()
        self.position = PositionScoreCalculator()
        self.timing = TimingScoreCalculator()

    def compute_composite(
        self,
        fund_code: str,
        fund_data: dict,
        kg: nx.DiGraph,
        events: list,
        llm_client: object | None = None,
    ) -> CompositeScore:
        """Compute full composite score for a fund.

        Args:
            fund_code: Fund identifier string.
            fund_data: Fund data dict with NAV, holdings, performance metrics.
            kg: NetworkX DiGraph built by KnowledgeGraphBuilder.
            events: List of event dicts.
            llm_client: Optional LLM client for enhanced scoring (stub).

        Returns:
            CompositeScore with all sub-scores, composite value, level, and regime.
        """
        # 1. Extract NAV series for regime detection
        nav_series = self._extract_nav_series(fund_data)

        # 2. Detect market regime
        regime = detect_regime(nav_series, events)

        # 3. Get regime-adaptive weights
        weights = get_regime_weights(regime)

        # 4. Compute all 5 sub-scores
        qs = self.quant.compute(fund_data, regime)
        fs = self.fundamental.compute(fund_data, kg, events, llm_client or self._llm_client)
        es = self.event_score.compute(fund_code, events, kg)
        ps = self.position.compute(fund_data, kg)
        ts = self.timing.compute(fund_data, regime, events, llm_client or self._llm_client)

        # 5. Weighted combination
        composite = (
            qs.score * weights["quant"]
            + fs.score * weights["fundamental"]
            + es.score * weights["event"]
            + ps.score * weights["position"]
            + ts.score * weights["timing"]
        )
        composite = round(composite, 2)

        # 6. Determine level
        level = score_level(composite)

        return CompositeScore(
            quant_score=qs,
            fundamental_score=fs,
            event_score=es,
            position_score=ps,
            timing_score=ts,
            weights_used=weights,
            composite=composite,
            level=level,
            regime=regime,
        )

    @staticmethod
    def _extract_nav_series(fund_data: dict) -> list[float]:
        """Extract NAV series from fund data for regime detection.

        Handles pandas DataFrame (from data pipeline) or raw list.
        """
        nav = fund_data.get("nav")
        if nav is None:
            return []
        if hasattr(nav, "columns") and "单位净值" in nav.columns:
            return nav["单位净值"].dropna().tolist()
        if isinstance(nav, list):
            return [float(x) for x in nav]
        return []
