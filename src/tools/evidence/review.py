"""Evidence review helpers.

This module exposes a pure evidence-review function for host agents. It is not
an agent loop and does not retry, replan, call LLMs, or perform network IO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.schemas.evidence_graph import EvidenceGraph


@dataclass
class EvidenceReviewResult:
    """Structured review result for an EvidenceGraph."""

    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=datetime.now)

    @property
    def status(self) -> str:
        return "PASS" if not self.issues else "BLOCKED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "issues": self.issues,
            "warnings": self.warnings,
            "missing_evidence": self.missing_evidence,
            "reviewed_at": self.reviewed_at.isoformat(),
        }


def review_evidence_graph(
    evidence_graph: EvidenceGraph,
    objective: str | None = None,
    risk_budget: dict | None = None,
) -> EvidenceReviewResult:
    """Review an EvidenceGraph without imposing an agent loop."""
    issues: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    items = getattr(evidence_graph, "items", {}) or {}
    if not items:
        issues.append("Missing evidence: graph is empty")
        missing.append("evidence")
    if getattr(evidence_graph, "hard_evidence_count", lambda: 0)() == 0:
        issues.append("Missing hard evidence")
        missing.append("hard_evidence")

    entity_soft_sources: dict[str, set[str]] = {}
    for item in items.values():
        if getattr(item, "evidence_type", "") == "SoftEvidence":
            for entity in getattr(item, "related_entities", []):
                entity_soft_sources.setdefault(entity, set()).add(item.source_type)
    single_source = sorted(
        entity for entity, sources in entity_soft_sources.items() if len(sources) == 1
    )
    if single_source:
        warnings.append(f"Single source soft evidence: {', '.join(single_source)}")

    conflicts = (
        evidence_graph.find_conflicts()
        if hasattr(evidence_graph, "find_conflicts")
        else []
    )
    if conflicts:
        issues.append(f"Unresolved conflicts: {len(conflicts)}")

    has_negative = any(getattr(item, "direction", "") == "negative" for item in items.values())
    if objective and "buy" in objective.lower() and not has_negative:
        warnings.append("Missing counter evidence for active buy objective")

    stale_cutoff = datetime.now() - timedelta(days=30)
    stale = [
        item.evidence_id
        for item in items.values()
        if getattr(item, "timestamp", datetime.now()) < stale_cutoff
    ]
    if stale:
        warnings.append(f"Evidence freshness issue: {len(stale)} stale item(s)")

    if risk_budget and not items:
        issues.append("Missing anchor for active decision support")
        missing.append("decision_anchor")

    return EvidenceReviewResult(
        issues=issues,
        warnings=warnings,
        missing_evidence=list(dict.fromkeys(missing)),
    )
