"""Quality facade -- stable public import path.

Exposes advisory quality gate evaluation and forbidden field validation.
"""
from __future__ import annotations

from src.tools.workflow.advisory_quality_gate import (
    compute_quality_status,
    evaluate_advisory_quality_gate,
)
from src.tools.workflow.report_safety import (
    FORBIDDEN_EXECUTION_FIELDS,
    find_forbidden_execution_fields,
)

__all__ = [
    "FORBIDDEN_EXECUTION_FIELDS",
    "evaluate_advisory_quality_gate",
    "compute_quality_status",
    "find_forbidden_execution_fields",
]
