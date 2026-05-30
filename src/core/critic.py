"""Critic — structural review of EvidenceGraph for decision readiness.

Reviews an EvidenceGraph against ResearchTask requirements, checking for:
- Missing HardEvidence coverage
- Single-source SoftEvidence bias
- Unresolved contradictions
- Missing risk evidence
- Untraceable nodes
- Inference leaps (SoftEvidence without HardEvidence support)

Returns a structured CritiqueResult (PASS / RETRY / FAIL / EXHAUSTED) with
actionable retry suggestions. Includes circuit breaker to prevent
infinite iteration loops.

Design constraints:
    * No LLM / network / IO imports — this is a pure review module.
    * Critic must NOT return only natural language — must return structured
      CritiqueResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

CritiqueStatus = Literal["PASS", "RETRY", "FAIL", "EXHAUSTED"]


@dataclass
class CritiqueResult:
    """Result of a critic review.

    Attributes:
        status: PASS (ready for decision), RETRY (fixable gaps found),
                FAIL (unrecoverable issues), or EXHAUSTED (retry budget spent
                with unresolved issues).
        issues: Human-readable descriptions of problems found.
        missing_evidence: Evidence categories or entities that are missing.
        retry_plan_suggestions: Actionable suggestions for the retry plan.
        reviewed_at: Timestamp of the review.
        iteration: Which iteration of the review loop this belongs to.
    """

    status: CritiqueStatus
    issues: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    retry_plan_suggestions: list[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=datetime.now)
    iteration: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "status": self.status,
            "issues": self.issues,
            "missing_evidence": self.missing_evidence,
            "retry_plan_suggestions": self.retry_plan_suggestions,
            "reviewed_at": self.reviewed_at.isoformat(),
            "iteration": self.iteration,
        }


class Critic:
    """Reviews EvidenceGraph against ResearchTask requirements.

    Performs 6 structural checks on the evidence graph:
    1. HardEvidence coverage (must have quantitative backing)
    2. Single-source bias (SoftEvidence from only one source)
    3. Unresolved contradictions (opposite directions on shared entities)
    4. Missing risk evidence (no risk/volatility/drawdown/sharpe claims)
    5. Untraceable nodes (evidence with no provenance)
    6. Inference leaps (SoftEvidence without supporting HardEvidence)

    Circuit breaker: returns EXHAUSTED after 3 iterations when issues remain.
    """

    MAX_ITERATIONS: int = 3

    # ── public API ────────────────────────────────────────────────────────────

    def review(
        self,
        task: Any,
        evidence_graph: Any,
        plan: Any = None,
        iteration: int = 0,
    ) -> CritiqueResult:
        """Review evidence graph for decision readiness.

        Args:
            task: ResearchTask with objective and constraints.
            evidence_graph: EvidenceGraph containing collected evidence items.
            plan: Optional Plan object (reserved for future use).
            iteration: Current review loop iteration (0-indexed).

        Returns:
            CritiqueResult with status, issues, and retry suggestions.
        """
        issues: list[str] = []
        missing: list[str] = []
        suggestions: list[str] = []

        # 1. Check for HardEvidence coverage
        hard_missing = self._check_hard_evidence(evidence_graph)
        if hard_missing:
            issues.append(f"Missing HardEvidence for: {', '.join(hard_missing)}")
            missing.extend(hard_missing)
            suggestions.append(
                f"Run quant analysis to generate HardEvidence for: {', '.join(hard_missing)}"
            )

        # 2. Check for single-source SoftEvidence bias
        single_source = self._check_single_source_bias(evidence_graph)
        if single_source:
            issues.append(
                f"Single-source SoftEvidence detected for: {', '.join(single_source)}"
            )
            suggestions.append(
                "Cross-validate with additional sources to upgrade to HybridEvidence"
            )

        # 3. Check for unprocessed contradictions
        contradictions = self._check_contradictions(evidence_graph)
        if contradictions:
            issues.append(f"Unresolved contradictions: {contradictions}")
            suggestions.append("Resolve contradictions before proceeding")

        # 4. Check for missing risk evidence
        risk_missing = self._check_missing_risk_evidence(evidence_graph)
        if risk_missing:
            issues.append("Missing risk-related evidence")
            missing.extend(risk_missing)
            suggestions.append(
                "Collect risk metrics: volatility, drawdown, Sharpe/Sortino ratios"
            )

        # 5. Check for untraceable nodes
        untraceable = self._check_untraceable_nodes(evidence_graph)
        if untraceable:
            issues.append(f"Untraceable evidence nodes: {untraceable}")
            suggestions.append(
                "Add provenance metadata to evidence items without source tracking"
            )

        # 6. Check for inference leaps (SoftEvidence without HardEvidence support)
        leaps = self._check_inference_leaps(evidence_graph)
        if leaps:
            issues.append(
                "Inference leap detected: SoftEvidence without supporting HardEvidence"
            )
            suggestions.append(
                "Back SoftEvidence claims with quantitative HardEvidence from tool output"
            )

        # ── Determine status ──────────────────────────────────────────────────

        if not issues:
            return CritiqueResult(status="PASS", iteration=iteration)

        if iteration >= self.MAX_ITERATIONS:
            return CritiqueResult(
                status="EXHAUSTED",
                issues=["Retry budget exhausted: max iterations reached"] + issues,
                missing_evidence=missing,
                retry_plan_suggestions=[],
                iteration=iteration,
            )

        # Critical issues → FAIL (not recoverable)
        if untraceable:
            return CritiqueResult(
                status="FAIL",
                issues=issues,
                missing_evidence=missing,
                retry_plan_suggestions=suggestions,
                iteration=iteration,
            )

        # Fixable issues → RETRY
        return CritiqueResult(
            status="RETRY",
            issues=issues,
            missing_evidence=missing,
            retry_plan_suggestions=suggestions,
            iteration=iteration,
        )

    # ── check helpers ─────────────────────────────────────────────────────────

    def _check_hard_evidence(self, evidence_graph) -> list[str]:
        """Check for missing HardEvidence.

        Returns list of entity categories missing hard evidence.
        Returns ["all"] when no HardEvidence exists at all.
        """
        if not evidence_graph or not getattr(evidence_graph, "items", None):
            return ["all"]

        hard_count = (
            evidence_graph.hard_evidence_count()
            if hasattr(evidence_graph, "hard_evidence_count")
            else 0
        )
        if hard_count == 0:
            return ["all"]
        return []

    def _check_single_source_bias(self, evidence_graph) -> list[str]:
        """Detect entities with only single-source SoftEvidence.

        Groups SoftEvidence by entity and source_type. Any entity that
        has SoftEvidence from only one source is flagged.
        """
        if not evidence_graph or not getattr(evidence_graph, "items", None):
            return []

        entity_sources: dict[str, set[str]] = {}
        for item in evidence_graph.items.values():
            etype = item.evidence_type if hasattr(item, "evidence_type") else "SoftEvidence"
            if etype == "SoftEvidence":
                for entity in item.related_entities:
                    if entity not in entity_sources:
                        entity_sources[entity] = set()
                    entity_sources[entity].add(item.source_type)

        return sorted(e for e, sources in entity_sources.items() if len(sources) == 1)

    def _check_contradictions(self, evidence_graph) -> list[str]:
        """Check for unresolved contradictions in the evidence graph.

        Delegates to EvidenceGraph.detect_conflicts() and formats
        the result as human-readable strings.
        """
        if not evidence_graph:
            return []
        conflicts = (
            evidence_graph.detect_conflicts()
            if hasattr(evidence_graph, "detect_conflicts")
            else []
        )
        return [f"{a} vs {b}" for a, b in conflicts]

    def _check_missing_risk_evidence(self, evidence_graph) -> list[str]:
        """Check for missing risk-related evidence claims.

        Scans claim text for risk-related keywords.
        """
        if not evidence_graph or not getattr(evidence_graph, "items", None):
            return ["risk_metrics"]

        has_risk = any(
            any(kw in item.claim.lower() for kw in ("risk", "volatility", "drawdown", "sharpe"))
            for item in evidence_graph.items.values()
            if hasattr(item, "claim")
        )
        return [] if has_risk else ["risk_metrics"]

    def _check_untraceable_nodes(self, evidence_graph) -> list[str]:
        """Check for evidence nodes without provenance.

        Evidence items with empty provenance dicts are considered
        untraceable — their origin cannot be audited.
        """
        if not evidence_graph or not getattr(evidence_graph, "items", None):
            return []

        untraceable: list[str] = []
        for eid, item in evidence_graph.items.items():
            provenance = item.provenance if hasattr(item, "provenance") else {}
            if not provenance:
                untraceable.append(eid)
        return untraceable

    def _check_inference_leaps(self, evidence_graph) -> list[str]:
        """Check for SoftEvidence without HardEvidence backing.

        Flagged when SoftEvidence items exist but no HardEvidence
        items are present in the graph.
        """
        if not evidence_graph or not getattr(evidence_graph, "items", None):
            return []

        soft_items = [
            item
            for item in evidence_graph.items.values()
            if hasattr(item, "evidence_type") and item.evidence_type == "SoftEvidence"
        ]
        hard_items = [
            item
            for item in evidence_graph.items.values()
            if hasattr(item, "evidence_type") and item.evidence_type == "HardEvidence"
        ]
        if soft_items and not hard_items:
            return ["SoftEvidence without HardEvidence support"]
        return []
