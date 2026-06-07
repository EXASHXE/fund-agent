"""Shared context structures for the fund analysis runtime pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.schemas.skill import SkillOutput


@dataclass(frozen=True)
class FundAnalysisContext:
    """Resolved input context passed from input/ledger stages into analysis."""

    payload: dict[str, Any]
    source_of_truth: str | None = None
    derived_snapshot: dict[str, Any] | None = None
    reconciliation_report: dict[str, Any] | None = None
    baseline_only: bool = False


@dataclass(frozen=True)
class StageResult:
    """Small result wrapper for stages that may short-circuit with SkillOutput."""

    context: FundAnalysisContext | None = None
    output: SkillOutput | None = None
