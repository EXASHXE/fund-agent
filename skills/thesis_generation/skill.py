"""Thesis Generation Skill — evidence synthesis to investment decisions.

Uses ToolRegistry for tool access. No direct network calls.
All synthesis and decision logic is rule-based.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.schemas import EvidenceItem, Direction
from src.schemas.decision import Decision, ActionType


@dataclass
class ThesisInput:
    """Typed input for thesis generation.

    Attributes:
        evidence_graph: For now, a list of EvidenceItems from all skills.
            In Phase 5, this will become a proper evidence graph structure.
        fund_analyses: List of FundAnalysisOutput objects from FundAnalysisSkill.
        risk_budget: Total risk budget for the portfolio (a float > 0).
    """
    evidence_graph: list[EvidenceItem]  # Will become graph in Phase 5
    fund_analyses: list[Any]  # List[FundAnalysisOutput]
    risk_budget: float


@dataclass
class ThesisOutput:
    """Typed output from thesis generation.

    Attributes:
        thesis_id: Unique identifier for this thesis.
        decisions: List of Decision objects for each fund.
        confidence: Overall confidence in this thesis [0, 1].
        counter_arguments: List of counter-argument strings to consider.
    """
    thesis_id: str
    decisions: list[Decision]
    confidence: float
    counter_arguments: list[str]


# Decision thresholds
_SCORE_INCREASE_THRESHOLD = 70.0  # Scores above this may trigger positive action
_SCORE_HOLD_STRONG_THRESHOLD = 75.0  # Scores above this trigger HOLD with positive evidence


class ThesisGenerationSkill:
    """Evidence synthesis and investment decision generation.

    Orchestrates:
        1. Evidence aggregation (positive vs negative per fund)
        2. Claim generation from evidence clusters
        3. Counter-argument identification
        4. Decision formulation per fund
        5. Confidence scoring

    Expected tools:
        - "evidence.rank": rank_by_relevance(items) -> list[EvidenceItem] (optional)
        - "evidence.counter_arguments": find_counter_arguments(claim) -> list[str] (optional)
        - All tools optional; pure logic fallback always works.
    """

    def __init__(self, tool_registry: Any):
        self.tools = tool_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, input_data: ThesisInput) -> ThesisOutput:
        """Execute thesis generation for all fund analyses.

        Pipeline:
            1. Aggregate evidence by fund code.
            2. Rank evidence by relevance and confidence.
            3. Generate claims per fund from evidence clusters.
            4. Identify counter-arguments.
            5. Formulate decisions per fund.
            6. Compute overall confidence.
        """
        evidence_items = input_data.evidence_graph
        fund_analyses = input_data.fund_analyses
        risk_budget = input_data.risk_budget

        thesis_id = f"thesis-{uuid.uuid4().hex[:12]}"

        if not fund_analyses:
            return ThesisOutput(
                thesis_id=thesis_id,
                decisions=[],
                confidence=0.0,
                counter_arguments=["无基金分析数据，无法生成投资决策"],
            )

        # ---- Step 1: Aggregate evidence by fund code --------------------
        evidence_by_fund: dict[str, list[EvidenceItem]] = {}
        for ev in evidence_items:
            for entity in ev.related_entities:
                if entity not in evidence_by_fund:
                    evidence_by_fund[entity] = []
                evidence_by_fund[entity].append(ev)

        # ---- Step 2-3: Rank evidence and generate claims ----------------
        all_decisions: list[Decision] = []
        total_confidence_weight = 0.0
        total_confidence_sum = 0.0
        all_counter_arguments: list[str] = []

        for analysis in fund_analyses:
            fund_code = analysis.fund_code if hasattr(analysis, "fund_code") else str(analysis)
            fund_evidence = evidence_by_fund.get(fund_code, [])
            fund_score = (
                analysis.overall_score
                if hasattr(analysis, "overall_score")
                else 50.0
            )

            # Rank evidence for this fund
            ranked_evidence = self._rank_evidence(fund_evidence)

            # Generate claims
            claims = self._generate_claims(ranked_evidence, analysis)

            # Find counter-arguments
            counter_args = self._find_counter_arguments(claims, ranked_evidence)
            all_counter_arguments.extend(counter_args)

            # Formulate decision
            decision = self._formulate_decision(
                fund_code=fund_code,
                score=fund_score,
                evidence=ranked_evidence,
                risk_budget=risk_budget,
            )
            all_decisions.append(decision)

            # Track confidence
            evidence_confidence = (
                sum(e.confidence_weight for e in ranked_evidence)
                / max(len(ranked_evidence), 1)
                if ranked_evidence else 0.5
            )
            total_confidence_sum += evidence_confidence
            total_confidence_weight += 1.0

        # ---- Step 6: Overall confidence ---------------------------------
        overall_confidence = (
            total_confidence_sum / total_confidence_weight
            if total_confidence_weight > 0
            else 0.5
        )

        # Deduplicate counter-arguments
        seen_args: set[str] = set()
        unique_counter_args: list[str] = []
        for arg in all_counter_arguments:
            if arg not in seen_args:
                seen_args.add(arg)
                unique_counter_args.append(arg)

        return ThesisOutput(
            thesis_id=thesis_id,
            decisions=all_decisions,
            confidence=round(overall_confidence, 4),
            counter_arguments=unique_counter_args[:5],  # Top 5
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _rank_evidence(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """Rank evidence items by relevance and confidence weight.

        Uses tool if available, else sorts by confidence_weight descending.
        """
        if not evidence:
            return []

        try:
            result = self.tools.invoke("evidence.rank", items=evidence)
            if isinstance(result, list) and all(
                isinstance(e, EvidenceItem) for e in result
            ):
                return result
        except (KeyError, TypeError, ValueError):
            pass

        # Fallback: sort by confidence_weight descending, then by direction
        # (negative evidence ranked higher for risk awareness)
        def sort_key(e: EvidenceItem) -> tuple:
            dir_order = {"negative": 0, "positive": 1, "neutral": 2}
            return (
                -e.confidence_weight,
                dir_order.get(e.direction, 2),
            )

        return sorted(evidence, key=sort_key)

    @staticmethod
    def _generate_claims(
        evidence: list[EvidenceItem], analysis: Any
    ) -> list[str]:
        """Generate human-readable claims from evidence clusters.

        Claims summarize the key findings per fund.
        """
        claims = []

        if hasattr(analysis, "overall_score"):
            score = analysis.overall_score
            if score >= 75:
                claims.append(f"基金综合评分 {score:.1f}，表现优秀")
            elif score >= 50:
                claims.append(f"基金综合评分 {score:.1f}，表现中等")
            else:
                claims.append(f"基金综合评分 {score:.1f}，需关注风险")

        if hasattr(analysis, "risk_signals"):
            for signal in analysis.risk_signals:
                claims.append(f"风险提示: {signal}")

        # Cluster evidence by direction
        positive = [e for e in evidence if e.direction == "positive"]
        negative = [e for e in evidence if e.direction == "negative"]

        if positive:
            top_pos = max(positive, key=lambda e: e.confidence_weight)
            claims.append(f"正面证据: {top_pos.claim}")

        if negative:
            top_neg = max(negative, key=lambda e: e.confidence_weight)
            claims.append(f"负面证据: {top_neg.claim}")

        if not claims:
            claims.append("暂无显著证据信号")

        return claims

    def _find_counter_arguments(
        self,
        claims: list[str],
        evidence: list[EvidenceItem],
    ) -> list[str]:
        """Find counter-arguments to the generated claims.

        Uses tool if available, otherwise extracts from negative evidence.
        """
        try:
            result = self.tools.invoke(
                "evidence.counter_arguments", claims=claims
            )
            if isinstance(result, list):
                return result
        except (KeyError, TypeError, ValueError):
            pass

        # Fallback: derive counter-arguments from negative evidence
        counter_args: list[str] = []
        negative = [e for e in evidence if e.direction == "negative"]
        for ev in negative[:3]:
            counter_args.append(f"反面意见: {ev.claim}")

        # If no negative evidence, generate generic counter-arguments
        if not counter_args:
            for claim in claims:
                if "表现优秀" in claim or "正面" in claim:
                    counter_args.append(
                        "历史表现不能保证未来收益，需关注市场风格切换风险"
                    )
                    break

        return counter_args

    def _formulate_decision(
        self,
        fund_code: str,
        score: float,
        evidence: list[EvidenceItem],
        risk_budget: float,
    ) -> Decision:
        """Formulate a single Decision for one fund based on evidence and score.

        Decision logic:
        - score >= 75 on positive evidence with no major negative -> HOLD/INCREASE
        - score >= 60 with mixed evidence -> HOLD
        - score 40-60 with negative evidence -> REDUCE
        - score < 40 with strong negative evidence -> WAIT
        """
        evidence_ids = [e.evidence_id for e in evidence]
        has_strong_negative = any(
            e.direction == "negative" and e.confidence_weight >= 0.7
            for e in evidence
        )
        has_strong_positive = any(
            e.direction == "positive" and e.confidence_weight >= 0.7
            for e in evidence
        )
        positive_count = sum(1 for e in evidence if e.direction == "positive")
        negative_count = sum(1 for e in evidence if e.direction == "negative")

        # Determine action — output HOLD/WAIT only. BUY/SELL decisions
        # are the exclusive responsibility of DecisionEngine.
        if score >= _SCORE_INCREASE_THRESHOLD and has_strong_positive and not has_strong_negative:
            action: ActionType = "HOLD"
            execution_amount = 0.0
        elif score >= _SCORE_HOLD_STRONG_THRESHOLD and has_strong_positive:
            action = "HOLD"
            execution_amount = 0.0
        elif score >= 60.0 and not has_strong_negative:
            action = "HOLD"
            execution_amount = 0.0
        elif score >= 40.0 and has_strong_negative:
            action = "WAIT"
            execution_amount = 0.0
        elif score < 40.0 or (has_strong_negative and negative_count > positive_count):
            action = "WAIT"
            execution_amount = 0.0
        else:
            action = "HOLD"
            execution_amount = 0.0

        # Trigger conditions
        trigger_conditions: list[str] = []
        if positive_count > negative_count:
            trigger_conditions.append(f"正面证据多于负面证据 ({positive_count} vs {negative_count})")
        if has_strong_positive:
            trigger_conditions.append("存在高置信度正面证据")
        if has_strong_negative:
            trigger_conditions.append("存在高置信度负面证据")
        if score >= 75:
            trigger_conditions.append(f"基金综合评分 >= 75 ({score:.1f})")
        elif score < 40:
            trigger_conditions.append(f"基金综合评分 < 40 ({score:.1f})")
        if not trigger_conditions:
            trigger_conditions.append(f"综合评分 {score:.1f}，证据方向均衡")

        # Invalidating conditions
        invalidating_conditions: list[str] = [
            "市场出现系统性风险事件",
            "基金基本面发生重大变化",
            "出现与现有证据矛盾的高置信度新证据",
        ]

        # Time horizon based on action
        time_horizons: dict[str, str] = {
            "HOLD": "中长期 (6-12个月)",
            "WAIT": "短期 (1-3个月)",
        }
        time_horizon = time_horizons.get(action, "中长期 (6-12个月)")

        decision_id = f"dec-{uuid.uuid4().hex[:12]}"

        return Decision(
            decision_id=decision_id,
            action=action,
            execution_amount=execution_amount,
            rationale_anchor=evidence_ids[:3] if evidence_ids else [decision_id],
            trigger_conditions=trigger_conditions,
            invalidating_conditions=invalidating_conditions,
            time_horizon=time_horizon,
            risk_budget=risk_budget * 0.1 if risk_budget > 0 else 1.0,
            audit_trail=evidence_ids,
        )
