"""QuantAgent graph node: quantitative scoring and market regime detection.

For each fund in state, computes QuantScore using QuantScoreCalculator and
detects the current market regime from NAV series and extracted events.
"""
from __future__ import annotations

import logging
from typing import Any

from src.agents.state import FundResearchState
from src.analysis.scoring.quant import QuantScoreCalculator
from src.analysis.scoring.regime import detect_regime
from src.analysis.scoring.types import MarketRegime, ScoreComponent

logger = logging.getLogger(__name__)


def _extract_nav_series(fund_data: dict) -> list[float]:
    """Extract NAV series from fund data for regime detection."""
    nav = fund_data.get("nav")
    if nav is None:
        return []
    if hasattr(nav, "columns") and "单位净值" in nav.columns:
        return nav["单位净值"].dropna().tolist()
    if isinstance(nav, list):
        return [float(x) for x in nav]
    return []


def quant_agent_node(state: FundResearchState) -> dict:
    """Compute quantitative scores and detect market regime for all funds.

    Reads funds_data and extracted_events from state. For each fund:
      1. Calls QuantScoreCalculator.compute(fund_data, regime)
      2. Uses NAV series + events for regime detection
      3. Updates quant_scores and market_regime in state.

    Args:
        state: FundResearchState with funds_data and optionally extracted_events.

    Returns:
        Dict with quant_scores and market_regime updates.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {"quant_scores": {}, "market_regime": "normal"}

    extracted_events = state.get("extracted_events", {})

    # Determine market regime: use first fund's NAV + all extracted events
    all_events: list[dict] = []
    for events_list in extracted_events.values():
        if isinstance(events_list, list):
            all_events.extend(events_list)

    regime: MarketRegime = MarketRegime.NORMAL
    try:
        # Use the first fund's NAV for regime detection
        for fund_data in funds_data.values():
            nav_series = _extract_nav_series(fund_data)
            if nav_series:
                regime = detect_regime(nav_series, all_events)
                break
    except Exception as exc:
        logger.warning("Regime detection failed, defaulting to NORMAL: %s", exc)

    # Compute quant scores per fund
    calculator = QuantScoreCalculator()
    quant_scores: dict[str, Any] = {}

    for fund_code, fund_data in funds_data.items():
        try:
            result: ScoreComponent = calculator.compute(fund_data, regime)
            quant_scores[fund_code] = result
        except Exception as exc:
            logger.error("Quant score failed for %s: %s", fund_code, exc)
            quant_scores[fund_code] = ScoreComponent(
                score=50.0, detail={"error": str(exc)}, weights={}, confidence=0.1,
            )

    return {
        "quant_scores": quant_scores,
        "market_regime": regime.value,
    }
