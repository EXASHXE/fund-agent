"""Compatibility wrapper -- delegates to the production regression runner.

The canonical implementation lives in
``src.skills_runtime.workflow.personal_regression``.  This module
re-exports everything so that existing ``from tests.helpers.personal_regression_runner import ...``
calls continue to work.
"""

from __future__ import annotations

from src.skills_runtime.workflow.personal_regression import (
    FORBIDDEN_EXECUTION_FIELDS,
    FIXTURES_DIR,
    REQUIRED_EXPECTED_KEYS,
    REQUIRED_FIXTURE_FIELDS,
    PersonalRegressionResult,
    fixture_from_result,
    flatten_report_text,
    list_personal_regression_fixtures,
    load_personal_regression_fixture,
    run_personal_regression_fixture,
    section_text,
    validate_personal_regression_result,
)

__all__ = [
    "FORBIDDEN_EXECUTION_FIELDS",
    "FIXTURES_DIR",
    "REQUIRED_EXPECTED_KEYS",
    "REQUIRED_FIXTURE_FIELDS",
    "PersonalRegressionResult",
    "fixture_from_result",
    "flatten_report_text",
    "list_personal_regression_fixtures",
    "load_personal_regression_fixture",
    "run_personal_regression_fixture",
    "section_text",
    "validate_personal_regression_result",
]
