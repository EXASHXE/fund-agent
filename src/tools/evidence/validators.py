"""Evidence validator functions — validation, dedup, conflict detection, aggregation, and compilation.

Provides:
- validate_evidence:      Validate a single EvidenceItem, returning error messages.
- deduplicate_evidence:   Remove near-duplicate claims from a list of items.
- detect_conflicts:       Find items with opposite directions on shared entities.
- aggregate_confidence:   Compute average confidence across all items.
- compile_evidence_graph: Assemble items into an EvidenceGraph.
"""

from __future__ import annotations

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


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


def compile_evidence_graph(items: list[EvidenceItem]) -> EvidenceGraph:
    """Compile a list of evidence items into an EvidenceGraph.

    Each item is added via EvidenceGraph.add(). No deduplication or
    validation is performed — use deduplicate_evidence() or
    validate_evidence() separately if needed.

    Args:
        items: List of EvidenceItem instances.

    Returns:
        EvidenceGraph containing all items.
    """
    graph = EvidenceGraph()
    for item in items:
        graph.add(item)
    return graph
