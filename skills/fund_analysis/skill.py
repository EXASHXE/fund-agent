"""Fund Analysis Skill — CIO-level strategic fund evaluation.

Uses ToolRegistry for tool access. No direct network calls.
All scoring logic is rule-based (thresholds, weighted averages).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.schemas import EvidenceItem, Direction


@dataclass
class FundAnalysisInput:
    """Typed input for fund analysis.

    Attributes:
        fund_code: The fund identifier (e.g. "000001").
        fund_data: Raw fund data dict (holdings, nav, daily_returns, etc.).
        kg_context: Knowledge graph context for this fund, from entity_chain.
            Expected keys: fund_exposure, industry_exposure, impact_chains.
        evidence_items: List of EvidenceItem instances related to this fund.
    """
    fund_code: str
    fund_data: dict[str, Any]
    kg_context: dict[str, Any]
    evidence_items: list[EvidenceItem]


@dataclass
class FundAnalysisOutput:
    """Typed output from fund analysis.

    Attributes:
        fund_code: The fund identifier.
        overall_score: Composite score (0-100).
        macro_assessment: Dict with macro-level analysis results.
        meso_assessment: Dict with meso-level (industry/sector) analysis.
        micro_assessment: Dict with micro-level (fund-specific) analysis.
        risk_signals: List of human-readable risk signals.
        evidence_ids: Evidence item IDs that contributed to this analysis.
    """
    fund_code: str
    overall_score: float
    macro_assessment: dict[str, Any]
    meso_assessment: dict[str, Any]
    micro_assessment: dict[str, Any]
    risk_signals: list[str]
    evidence_ids: list[str]


class FundAnalysisSkill:
    """CIO-level strategic fund analysis.

    Orchestrates: KG queries -> quant scoring -> risk assessment -> synthesis.

    Args:
        tool_registry: A ToolRegistry instance for invoking tools.
            Expected tools:
            - "sortino_ratio": sortino_ratio(daily_returns) -> float
            - "compute_hhi": compute_hhi(holdings_df) -> float | None
            - "compute_perf": compute_perf_from_nav(nav_df) -> dict
            - "compute_correlations": (data) -> DataFrame
            - "score_helpers": score_sortino(sortino), score_drawdown(dd), etc.
            All tools are optional; missing tools result in graceful fallback.
    """

    def __init__(self, tool_registry: Any):
        self.tools = tool_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, input_data: FundAnalysisInput) -> FundAnalysisOutput:
        """Execute fund analysis using available tools.

        Pipeline:
            1. Extract fund exposure and industry context from KG context.
            2. Compute risk metrics via tools (Sortino, HHI, Alpha) with fallback.
            3. Aggregate evidence items by direction.
            4. Score macro (20%), meso (30%), micro (50%) dimensions.
            5. Compute composite score.
            6. Generate risk signals.
            7. Return structured FundAnalysisOutput.
        """
        fund_code = input_data.fund_code
        fund_data = input_data.fund_data
        kg_context = input_data.kg_context
        evidence_items = input_data.evidence_items

        # ---- Step 1: Extract KG exposure ---------------------------------
        fund_exposure = kg_context.get("fund_exposure", {})
        industry_exposure = kg_context.get("industry_exposure", {})
        impact_chains = kg_context.get("impact_chains", {})

        # ---- Step 2: Compute risk metrics via tools (with fallback) ------
        sortino = self._compute_sortino(fund_data)
        hhi = self._compute_hhi(fund_data)
        perf = self._compute_perf(fund_data)
        alpha = self._extract_alpha(perf)
        sharpe = self._extract_sharpe(perf)
        volatility = self._extract_volatility(perf)
        max_drawdown = self._extract_drawdown(perf)

        # ---- Step 3: Aggregate evidence by direction --------------------
        positive_evidence = [e for e in evidence_items if e.direction == "positive"]
        negative_evidence = [e for e in evidence_items if e.direction == "negative"]
        neutral_evidence = [e for e in evidence_items if e.direction == "neutral"]

        # ---- Step 4: Dimension scores ------------------------------------
        macro_score = self._compute_macro_score(
            fund_data=fund_data,
            kg_context=kg_context,
            impact_chains=impact_chains,
        )
        meso_score = self._compute_meso_score(
            fund_data=fund_data,
            industry_exposure=industry_exposure,
            hhi=hhi,
            evidence_items=evidence_items,
        )
        micro_score = self._compute_micro_score(
            sortino=sortino,
            sharpe=sharpe,
            alpha=alpha,
            volatility=volatility,
            max_drawdown=max_drawdown,
            positive_count=len(positive_evidence),
            negative_count=len(negative_evidence),
        )

        # ---- Step 5: Composite score (macro 20%, meso 30%, micro 50%) ----
        overall_score = round(
            0.20 * macro_score + 0.30 * meso_score + 0.50 * micro_score, 2
        )
        overall_score = min(100.0, max(0.0, overall_score))

        # ---- Step 6: Risk signals ---------------------------------------
        risk_signals = self._generate_risk_signals(
            fund_data=fund_data,
            sortino=sortino,
            hhi=hhi,
            alpha=alpha,
            volatility=volatility,
            max_drawdown=max_drawdown,
            negative_evidence=negative_evidence,
            impact_chains=impact_chains,
        )

        # ---- Step 7: Build output ---------------------------------------
        macro_assessment = {
            "score": macro_score,
            "fund_type": fund_data.get("fund_type", ""),
            "fund_name": fund_data.get("fund_name", ""),
            "market_regime": kg_context.get("market_regime", "unknown"),
            "impact_event_count": len(impact_chains.get("events", [])),
        }

        meso_assessment = {
            "score": meso_score,
            "industry_exposure": {
                k: round(v, 4) for k, v in industry_exposure.items()
            } if industry_exposure else {},
            "hhi": hhi,
            "holdings_count": (
                len(fund_data.get("holdings", []))
                if isinstance(fund_data.get("holdings"), (list, type(None)))
                else 0
            ),
        }

        micro_assessment = {
            "score": micro_score,
            "sortino_ratio": sortino,
            "sharpe_ratio": sharpe,
            "jensen_alpha": alpha,
            "annual_volatility": volatility,
            "max_drawdown": max_drawdown,
            "positive_evidence_count": len(positive_evidence),
            "negative_evidence_count": len(negative_evidence),
            "neutral_evidence_count": len(neutral_evidence),
        }

        evidence_ids = [e.evidence_id for e in evidence_items]

        return FundAnalysisOutput(
            fund_code=fund_code,
            overall_score=overall_score,
            macro_assessment=macro_assessment,
            meso_assessment=meso_assessment,
            micro_assessment=micro_assessment,
            risk_signals=risk_signals,
            evidence_ids=evidence_ids,
        )

    # ------------------------------------------------------------------
    # Tool invocation helpers (with graceful fallback)
    # ------------------------------------------------------------------

    def _compute_sortino(self, fund_data: dict) -> float | None:
        """Compute Sortino ratio via tool, or fallback to raw data value."""
        daily_returns = fund_data.get("daily_returns")
        if daily_returns:
            try:
                return float(self.tools.invoke("sortino_ratio", daily_returns=daily_returns))
            except (KeyError, TypeError, ValueError):
                pass
        # Fallback: use pre-computed value from fund_data
        raw = fund_data.get("sortino_ratio")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        return None

    def _compute_hhi(self, fund_data: dict) -> float | None:
        """Compute HHI via tool, or fallback to raw data value."""
        holdings_df = fund_data.get("holdings")
        if holdings_df is not None:
            try:
                result = self.tools.invoke("compute_hhi", holdings_df=holdings_df)
                if result is not None:
                    return float(result)
            except (KeyError, TypeError, ValueError):
                pass
        # Fallback
        raw = fund_data.get("hhi_index")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        return None

    def _compute_perf(self, fund_data: dict) -> dict:
        """Compute performance metrics via tool, or return empty dict."""
        nav_df = fund_data.get("nav")
        if nav_df is not None:
            try:
                result = self.tools.invoke("compute_perf_from_nav", nav_df=nav_df)
                if isinstance(result, dict):
                    return result
            except (KeyError, TypeError, ValueError):
                pass
        # Fallback: extract from fund_data
        perf = fund_data.get("performance", {})
        if isinstance(perf, dict):
            return perf
        return {}

    @staticmethod
    def _extract_alpha(perf: dict) -> float | None:
        """Extract Jensen Alpha from performance dict."""
        alpha = perf.get("近1年", {}).get("jensen_alpha")
        if alpha is not None:
            return float(alpha)
        return perf.get("jensen_alpha")

    @staticmethod
    def _extract_sharpe(perf: dict) -> float | None:
        """Extract Sharpe ratio from performance dict."""
        sharpe = perf.get("近1年", {}).get("sharpe_ratio")
        if sharpe is not None:
            return float(sharpe)
        return perf.get("sharpe_ratio")

    @staticmethod
    def _extract_volatility(perf: dict) -> float | None:
        """Extract annual volatility from performance dict."""
        vol = perf.get("近1年", {}).get("annual_volatility")
        if vol is not None:
            return float(vol)
        return perf.get("annual_volatility")

    @staticmethod
    def _extract_drawdown(perf: dict) -> float | None:
        """Extract max drawdown from performance dict."""
        dd = perf.get("近1年", {}).get("max_drawdown")
        if dd is not None:
            return float(dd)
        return perf.get("max_drawdown")

    # ------------------------------------------------------------------
    # Pure scoring logic (no tool calls)
    # ------------------------------------------------------------------

    def _compute_macro_score(
        self,
        fund_data: dict,
        kg_context: dict,
        impact_chains: dict,
    ) -> float:
        """Macro-level score: fund type fit, market correlation, external events.

        Scoring logic (pure rule-based):
        - Fund type baseline: 股票型=60, 混合型=65, 债券型=75, 货币型=80
        - Market regime adjustment: +10 if favorable, -10 if adverse
        - Event impact: -5 per negative event in impact chain
        """
        fund_type = fund_data.get("fund_type", "")
        type_baselines = {
            "股票型": 60.0,
            "混合型": 65.0,
            "债券型": 75.0,
            "货币型": 80.0,
            "指数型": 65.0,
            "QDII": 55.0,
            "FOF": 65.0,
        }
        score = 60.0
        for key, base in type_baselines.items():
            if key in fund_type:
                score = base
                break

        # Market regime adjustment
        regime = kg_context.get("market_regime", "").lower()
        regime_adjustments = {
            "bull": 10,
            "normal": 0,
            "bear": -10,
            "high_volatility": -5,
            "crisis": -15,
        }
        score += regime_adjustments.get(regime, 0)

        # Event impact
        events = impact_chains.get("events", [])
        for event in events:
            impact = event.get("impact", "").lower()
            if impact in ("negative", "adverse"):
                score -= 5.0

        return min(100.0, max(0.0, score))

    def _compute_meso_score(
        self,
        fund_data: dict,
        industry_exposure: dict,
        hhi: float | None,
        evidence_items: list,
    ) -> float:
        """Meso-level score: industry diversification, concentration, sector quality.

        Scoring logic (pure rule-based):
        - HHI: <1500 -> 80, 1500-2500 -> 60, >2500 -> 40
        - Number of industries: >=5 -> 80, 3-4 -> 60, <3 -> 40
        - Sector quality: cyclical discount, defensive premium
        """
        # HHI score
        hhi_score = 60.0
        if hhi is not None:
            if hhi < 1500:
                hhi_score = 80.0
            elif hhi <= 2500:
                hhi_score = 60.0
            else:
                hhi_score = 40.0

        # Industry diversification
        industry_count = len(industry_exposure) if industry_exposure else 0
        if industry_count >= 5:
            industry_score = 80.0
        elif industry_count >= 3:
            industry_score = 60.0
        elif industry_count >= 1:
            industry_score = 40.0
        else:
            industry_score = 50.0  # neutral when unknown

        # Evidence sentiment adjustment
        evidence_adjustment = 0.0
        positive_meso = sum(
            1 for e in evidence_items
            if e.direction == "positive" and "sector" in e.source_type.lower()
        )
        negative_meso = sum(
            1 for e in evidence_items
            if e.direction == "negative" and "sector" in e.source_type.lower()
        )
        if positive_meso + negative_meso > 0:
            evidence_adjustment = (positive_meso - negative_meso) / (
                positive_meso + negative_meso
            ) * 10.0

        # Weighted: 50% HHI, 30% industry count, 20% evidence
        score = 0.50 * hhi_score + 0.30 * industry_score + 0.20 * (60.0 + evidence_adjustment)
        return min(100.0, max(0.0, score))

    def _compute_micro_score(
        self,
        sortino: float | None,
        sharpe: float | None,
        alpha: float | None,
        volatility: float | None,
        max_drawdown: float | None,
        positive_count: int,
        negative_count: int,
    ) -> float:
        """Micro-level score: risk-adjusted returns, fund-specific metrics.

        Scoring logic (pure rule-based):
        - Sortino: >1.5 -> 80, >1.0 -> 65, >0.5 -> 50, >0 -> 40, else 30
        - Sharpe:  >1.5 -> 80, >1.0 -> 65, >0.5 -> 50, >0 -> 40, else 30
        - Alpha:   >0.08 -> 80, >0.03 -> 65, >0 -> 50, >-0.05 -> 40, else 30
        - Volatility: <10 -> 80, <15 -> 65, <20 -> 50, <25 -> 40, else 30
        - Drawdown: <10 -> 80, <15 -> 65, <20 -> 50, <25 -> 40, else 30
        - Evidence: net positive sentiment adjustment
        """
        scores = []

        # Sortino score
        if sortino is not None:
            if sortino > 1.5:
                scores.append(80.0)
            elif sortino > 1.0:
                scores.append(65.0)
            elif sortino > 0.5:
                scores.append(50.0)
            elif sortino > 0.0:
                scores.append(40.0)
            else:
                scores.append(30.0)

        # Sharpe score
        if sharpe is not None:
            if sharpe > 1.5:
                scores.append(80.0)
            elif sharpe > 1.0:
                scores.append(65.0)
            elif sharpe > 0.5:
                scores.append(50.0)
            elif sharpe > 0.0:
                scores.append(40.0)
            else:
                scores.append(30.0)

        # Alpha score
        if alpha is not None:
            if alpha > 0.08:
                scores.append(80.0)
            elif alpha > 0.03:
                scores.append(65.0)
            elif alpha > 0.0:
                scores.append(50.0)
            elif alpha > -0.05:
                scores.append(40.0)
            else:
                scores.append(30.0)

        # Volatility score (lower is better)
        if volatility is not None:
            if volatility < 10:
                scores.append(80.0)
            elif volatility < 15:
                scores.append(65.0)
            elif volatility < 20:
                scores.append(50.0)
            elif volatility < 25:
                scores.append(40.0)
            else:
                scores.append(30.0)

        # Max drawdown score (lower is better)
        if max_drawdown is not None:
            if max_drawdown < 10:
                scores.append(80.0)
            elif max_drawdown < 15:
                scores.append(65.0)
            elif max_drawdown < 20:
                scores.append(50.0)
            elif max_drawdown < 25:
                scores.append(40.0)
            else:
                scores.append(30.0)

        # If no metrics available, return neutral score
        if not scores:
            return 50.0

        # Average available scores
        base_score = sum(scores) / len(scores)

        # Evidence sentiment adjustment (±10 max)
        total_evidence = positive_count + negative_count
        if total_evidence > 0:
            net_sentiment = (positive_count - negative_count) / total_evidence
            base_score += net_sentiment * 10.0

        return min(100.0, max(0.0, base_score))

    def _generate_risk_signals(
        self,
        fund_data: dict,
        sortino: float | None,
        hhi: float | None,
        alpha: float | None,
        volatility: float | None,
        max_drawdown: float | None,
        negative_evidence: list,
        impact_chains: dict,
    ) -> list[str]:
        """Generate human-readable risk signals from all analysis dimensions."""
        signals = []

        if sortino is not None and sortino < 0.5:
            signals.append(f"Sortino ratio 偏低 ({sortino:.2f})，风险调整后收益不足")

        if hhi is not None and hhi > 2500:
            signals.append(f"持仓集中度偏高 (HHI={hhi:.1f})，集中度风险")
        elif hhi is not None and hhi > 3500:
            signals.append(f"持仓高度集中 (HHI={hhi:.1f})，分散化不足")

        if alpha is not None and alpha < -0.03:
            signals.append(f"Jensen Alpha 为负 ({alpha:.4f})，基金未跑赢基准")

        if volatility is not None and volatility > 25:
            signals.append(f"年化波动率偏高 ({volatility:.1f}%)，波动风险较大")

        if max_drawdown is not None and max_drawdown > 20:
            signals.append(f"最大回撤偏高 ({max_drawdown:.1f}%)，下行风险显著")

        for ev in negative_evidence[:3]:
            signals.append(f"负面证据: {ev.claim[:60]}")

        events = impact_chains.get("events", [])
        negative_events = [e for e in events if e.get("impact", "").lower() == "negative"]
        for event in negative_events[:2]:
            signals.append(
                f"事件冲击: {event.get('description', event.get('name', '未知事件'))}"
            )

        # Fund type-specific signals
        fund_type = fund_data.get("fund_type", "")
        if "QDII" in fund_type or "QDII" in str(fund_data.get("fund_name", "")):
            signals.append("QDII 基金存在汇率风险与跨境结算延迟")

        return signals
