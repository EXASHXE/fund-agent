"""Regression facade -- stable public import path.

Exposes personal regression runner types and helpers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.workflow.advisory_intent import classify_advisory_intent
from src.skills_runtime.workflow.evidence_bridge import (
    WorkflowEvidenceGraphResult,
    build_evidence_graph_from_workflow,
)
from src.skills_runtime.workflow.workflow_trace import WorkflowTrace
from src.tools.workflow.advisory_quality_gate import evaluate_advisory_quality_gate
from src.tools.workflow.final_report import compose_advisory_workflow_report

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "personal_portfolio_regressions"
)


def list_personal_regression_fixtures() -> list[Path]:
    if not FIXTURES_DIR.exists():
        return []
    return sorted(p for p in FIXTURES_DIR.glob("*.json") if p.is_file())


def load_personal_regression_fixture(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def run_personal_regression_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    from tests.helpers.personal_regression_runner import (
        run_personal_regression_fixture as _run,
    )
    return _run(fixture)


def validate_personal_regression_result(
    result: dict[str, Any],
    fixture: dict[str, Any],
) -> list[str]:
    from tests.helpers.personal_regression_runner import (
        validate_personal_regression_result as _validate,
    )
    return _validate(result, fixture)


class PersonalRegressionResult:
    __slots__ = ("fixture_path", "fixture", "result", "validation_errors")

    def __init__(
        self,
        fixture_path: Path,
        fixture: dict[str, Any],
        result: dict[str, Any],
        validation_errors: list[str],
    ) -> None:
        self.fixture_path = fixture_path
        self.fixture = fixture
        self.result = result
        self.validation_errors = validation_errors

    @property
    def ok(self) -> bool:
        return len(self.validation_errors) == 0


__all__ = [
    "FIXTURES_DIR",
    "PersonalRegressionResult",
    "list_personal_regression_fixtures",
    "load_personal_regression_fixture",
    "run_personal_regression_fixture",
    "validate_personal_regression_result",
]
