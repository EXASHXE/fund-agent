"""Evidence tools — builders and validators for EvidenceGraph compilation."""

from src.tools.evidence.builders import build_hard_evidence, build_hybrid_evidence, build_soft_evidence
from src.tools.evidence.validators import (
    EvidenceGraphCompileReport,
    aggregate_confidence,
    compile_evidence_graph,
    deduplicate_evidence,
    detect_conflicts,
    validate_evidence,
)

__all__ = [
    "build_hard_evidence",
    "build_soft_evidence",
    "build_hybrid_evidence",
    "EvidenceGraphCompileReport",
    "validate_evidence",
    "deduplicate_evidence",
    "detect_conflicts",
    "aggregate_confidence",
    "compile_evidence_graph",
]
