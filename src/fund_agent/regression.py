"""Regression facade -- stable public import path.

Exposes personal regression runner types and helpers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.skills_runtime.workflow.personal_regression import (
    PersonalRegressionResult,
    list_personal_regression_fixtures,
    load_personal_regression_fixture,
    run_personal_regression_fixture,
    validate_personal_regression_result,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "personal_portfolio_regressions"
)


__all__ = [
    "FIXTURES_DIR",
    "PersonalRegressionResult",
    "list_personal_regression_fixtures",
    "load_personal_regression_fixture",
    "run_personal_regression_fixture",
    "validate_personal_regression_result",
]
