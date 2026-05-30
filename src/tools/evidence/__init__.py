"""Evidence tools — builders and validators for EvidenceGraph compilation."""

from src.tools.evidence.builders import (
    build_hard_evidence,
    build_hard_evidence_from_metric,
    build_hybrid_evidence,
    build_hybrid_evidence_from_supporting_items,
    build_soft_evidence,
    build_soft_evidence_from_mcp_result,
    build_soft_evidence_from_sentiment,
)
from src.tools.evidence.validators import (
    EvidenceGraphCompileReport,
    EvidenceGraphCompileResult,
    aggregate_confidence,
    compile_evidence_graph,
    deduplicate_evidence,
    detect_conflicts,
    validate_evidence,
)

__all__ = [
    "build_hard_evidence",
    "build_hard_evidence_from_metric",
    "build_soft_evidence",
    "build_soft_evidence_from_mcp_result",
    "build_soft_evidence_from_sentiment",
    "build_hybrid_evidence",
    "build_hybrid_evidence_from_supporting_items",
    "EvidenceGraphCompileReport",
    "EvidenceGraphCompileResult",
    "validate_evidence",
    "deduplicate_evidence",
    "detect_conflicts",
    "aggregate_confidence",
    "compile_evidence_graph",
]
