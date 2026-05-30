"""Evidence validator functions — validation, dedup, conflict detection, aggregation, and compilation.

Provides:
- validate_evidence:      Validate a single EvidenceItem, returning error messages.
- deduplicate_evidence:   Remove near-duplicate claims from a list of items.
- detect_conflicts:       Find items with opposite directions on shared entities.
- aggregate_confidence:   Compute average confidence across all items.
- compile_evidence_graph: Assemble items into an EvidenceGraph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


@dataclass
class EvidenceGraphCompileReport:
    """Structured result from EvidenceGraph compilation."""

    graph: EvidenceGraph
    input_count: int = 0
    accepted_count: int = 0
    rejected_items: list[dict[str, Any]] = field(default_factory=list)
    duplicate_removed_ids: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    hybrid_upgraded_ids: list[str] = field(default_factory=list)
    confidence_by_entity: dict[str, float] = field(default_factory=dict)
    average_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_dict(),
            "input_count": self.input_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "rejected_items": self.rejected_items,
            "duplicate_removed_ids": self.duplicate_removed_ids,
            "conflicts": [list(pair) for pair in self.conflicts],
            "hybrid_upgraded_ids": self.hybrid_upgraded_ids,
            "confidence_by_entity": self.confidence_by_entity,
            "average_confidence": self.average_confidence,
            "warnings": self.warnings,
        }

    def __getattr__(self, name: str) -> Any:
        """Delegate legacy graph-style attribute access to the compiled graph."""
        return getattr(self.graph, name)


def validate_evidence(item: EvidenceItem) -> list[str]:
    """Validate a single evidence item. Returns list of error messages (empty = valid).

    Checks:
    - source_type must be present
    - timestamp must be present
    - related_entities must be non-empty
    - HardEvidence must have confidence_weight == 1.0
    - SoftEvidence/HybridEvidence must have confidence_weight in [0.1, 1.0]

    Args:
        item: The EvidenceItem to validate.

    Returns:
        List of human-readable error messages. Empty list means valid.
    """
    errors: list[str] = []

    if not item.source_type:
        errors.append("Missing source_type")
    if not item.timestamp:
        errors.append("Missing timestamp")
    if not item.related_entities:
        errors.append("Missing related_entities")
    if item.evidence_type == "HardEvidence" and item.confidence_weight != 1.0:
        errors.append(
            f"HardEvidence confidence must be 1.0, got {item.confidence_weight}"
        )
    if item.evidence_type in ("SoftEvidence", "HybridEvidence"):
        if not (0.1 <= item.confidence_weight <= 1.0):
            errors.append(
                f"Soft/Hybrid confidence must be [0.1, 1.0], "
                f"got {item.confidence_weight}"
            )
    return errors


def deduplicate_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Remove near-duplicate evidence items from a list.

    Delegates to EvidenceGraph.deduplicate() which compares claim similarity
    and entity overlap.

    Args:
        items: List of EvidenceItem instances.

    Returns:
        Deduplicated list of EvidenceItem instances.
    """
    if not items:
        return []

    graph = EvidenceGraph()
    for item in items:
        graph.add(item)
    graph.deduplicate()
    return list(graph.items.values())


def detect_conflicts(items: list[EvidenceItem]) -> list[tuple[str, str, str]]:
    """Detect conflicts between evidence items with opposite directions on shared entities.

    Delegates to EvidenceGraph.detect_conflicts().

    Args:
        items: List of EvidenceItem instances.

    Returns:
        List of (from_id, to_id, reason) tuples describing conflicts.
    """
    if not items:
        return []

    graph = EvidenceGraph()
    for item in items:
        graph.add(item)
    raw_conflicts = graph.detect_conflicts()
    return [(from_id, to_id, "contradiction") for from_id, to_id in raw_conflicts]


def aggregate_confidence(items: list[EvidenceItem]) -> float:
    """Compute the average confidence across all evidence items.

    Args:
        items: List of EvidenceItem instances.

    Returns:
        Average confidence_weight. Returns 0.0 for empty list.
    """
    if not items:
        return 0.0
    total = sum(item.confidence_weight for item in items)
    return total / len(items)


def compile_evidence_graph(items: list[EvidenceItem]) -> EvidenceGraphCompileReport:
    """Compile evidence through the full contract pipeline.

    Pipeline order:
    validate → reject invalid → deduplicate → detect conflicts →
    hybrid upgrade → confidence aggregation.

    Args:
        items: List of EvidenceItem instances.

    Returns:
        EvidenceGraphCompileReport containing the graph and compile metadata.
    """
    input_count = len(items)
    rejected_items: list[dict[str, Any]] = []
    valid_items: list[EvidenceItem] = []

    for item in items:
        errors = validate_evidence(item)
        if errors:
            rejected_items.append(
                {
                    "evidence_id": getattr(item, "evidence_id", ""),
                    "errors": errors,
                }
            )
            continue
        valid_items.append(item)

    graph = EvidenceGraph()
    for item in valid_items:
        graph.add(item)

    duplicate_removed_ids = graph.deduplicate()
    conflicts = graph.detect_conflicts()
    hybrid_upgraded_ids = _upgrade_corroborated_soft_evidence(graph)
    confidence_by_entity = _aggregate_confidence_by_entity(graph)

    return EvidenceGraphCompileReport(
        graph=graph,
        input_count=input_count,
        accepted_count=len(graph.items),
        rejected_items=rejected_items,
        duplicate_removed_ids=duplicate_removed_ids,
        conflicts=conflicts,
        hybrid_upgraded_ids=hybrid_upgraded_ids,
        confidence_by_entity=confidence_by_entity,
        average_confidence=aggregate_confidence(list(graph.items.values())),
        warnings=[
            f"Rejected {len(rejected_items)} invalid evidence item(s)"
        ] if rejected_items else [],
    )


def _upgrade_corroborated_soft_evidence(graph: EvidenceGraph) -> list[str]:
    """Upgrade SoftEvidence when 2+ distinct sources corroborate an entity."""
    groups: dict[tuple[tuple[str, ...], str], list[EvidenceItem]] = {}
    for item in graph.items.values():
        if item.evidence_type != "SoftEvidence":
            continue
        key = (tuple(sorted(item.related_entities)), item.direction)
        groups.setdefault(key, []).append(item)

    upgraded: list[str] = []
    for group in groups.values():
        distinct_sources = {item.source_type for item in group}
        if len(distinct_sources) < 2:
            continue
        target = group[0]
        supporting_ids = [
            item.evidence_id
            for item in group[1:]
            if item.evidence_id in graph.items
        ]
        if not supporting_ids:
            continue
        result = graph.upgrade_to_hybrid(target.evidence_id, supporting_ids)
        if result is not None:
            upgraded.append(result.evidence_id)
    return upgraded


def _aggregate_confidence_by_entity(graph: EvidenceGraph) -> dict[str, float]:
    entities = {
        entity
        for item in graph.items.values()
        for entity in item.related_entities
    }
    return {
        entity: graph.aggregate_confidence(entity)
        for entity in sorted(entities)
    }
