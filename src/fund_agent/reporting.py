"""Reporting facade -- stable public import path.

Exposes report composition and status helpers.
"""
from __future__ import annotations

from src.tools.workflow.final_report import compose_advisory_workflow_report
from src.tools.workflow.report_status import (
    compute_decision_status,
    compute_report_status,
    data_completeness_grade,
)

__all__ = [
    "compose_advisory_workflow_report",
    "compute_decision_status",
    "compute_report_status",
    "data_completeness_grade",
]
