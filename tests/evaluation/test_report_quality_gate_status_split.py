"""Tests for compute_quality_status() — Task 6 quality gate status split."""

from __future__ import annotations

import pytest

from src.tools.workflow.advisory_quality_gate import compute_quality_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qg_result(
    *,
    passed: bool = True,
    fail_count: int = 0,
    warn_count: int = 0,
    checks: list[dict] | None = None,
) -> dict:
    """Build a minimal quality_gate_result dict."""
    if checks is None:
        checks = []
    return {
        "passed": passed,
        "summary": {"fail_count": fail_count, "warn_count": warn_count},
        "checks": checks,
    }


def _dc(
    *,
    grade: str = "A",
    score: float = 0.95,
    missing_sections: list[str] | None = None,
    critical_missing: list[str] | None = None,
) -> dict:
    """Build a minimal data_completeness dict."""
    return {
        "grade": grade,
        "score": score,
        "missing_sections": missing_sections or [],
        "critical_missing": critical_missing or [],
    }


# ---------------------------------------------------------------------------
# pipeline_status
# ---------------------------------------------------------------------------


class TestPipelineStatus:
    def test_pipeline_status_success_when_no_failures(self):
        qg = _qg_result(passed=True, fail_count=0, warn_count=0)
        result = compute_quality_status(qg, _dc())
        assert result["pipeline_status"] == "SUCCESS"

    def test_pipeline_status_partial_when_warnings(self):
        qg = _qg_result(passed=False, fail_count=0, warn_count=2)
        result = compute_quality_status(qg, _dc())
        assert result["pipeline_status"] == "PARTIAL"

    def test_pipeline_status_partial_when_failures(self):
        qg = _qg_result(passed=False, fail_count=1, warn_count=0)
        result = compute_quality_status(qg, _dc())
        assert result["pipeline_status"] == "PARTIAL"

    def test_pipeline_status_failed_when_engineering_failure(self):
        """Hard engineering failure should override pipeline_status to FAILED."""
        qg = _qg_result(
            passed=False,
            fail_count=1,
            warn_count=0,
            checks=[
                {"id": "active_trade_anchor_gate", "status": "FAIL"},
            ],
        )
        result = compute_quality_status(qg, _dc())
        assert result["pipeline_status"] == "FAILED"
        assert result["engineering_status"] == "FAILED"


# ---------------------------------------------------------------------------
# data_readiness_status
# ---------------------------------------------------------------------------


class TestDataReadinessStatus:
    def test_data_readiness_complete_grade_a(self):
        result = compute_quality_status(_qg_result(), _dc(grade="A", score=0.95))
        assert result["data_readiness_status"] == "COMPLETE"

    def test_data_readiness_complete_grade_b(self):
        result = compute_quality_status(_qg_result(), _dc(grade="B", score=0.80))
        assert result["data_readiness_status"] == "COMPLETE"

    def test_data_readiness_incomplete_grade_c(self):
        result = compute_quality_status(_qg_result(), _dc(grade="C", score=0.50))
        assert result["data_readiness_status"] == "INCOMPLETE"

    def test_data_readiness_incomplete_grade_d(self):
        """Grade D without core missing should be INCOMPLETE (not BLOCKED)."""
        result = compute_quality_status(_qg_result(), _dc(grade="D", score=0.20))
        assert result["data_readiness_status"] == "INCOMPLETE"

    def test_data_readiness_blocked_missing_core(self):
        """Critical missing core sections should block data readiness."""
        result = compute_quality_status(
            _qg_result(),
            _dc(
                grade="C",
                score=0.50,
                critical_missing=["Portfolio Snapshot"],
            ),
        )
        assert result["data_readiness_status"] == "BLOCKED_BY_MISSING_CORE_DATA"

    def test_data_readiness_blocked_missing_current_value(self):
        result = compute_quality_status(
            _qg_result(),
            _dc(
                grade="B",
                score=0.75,
                critical_missing=["Current Value Or Nav"],
            ),
        )
        assert result["data_readiness_status"] == "BLOCKED_BY_MISSING_CORE_DATA"


# ---------------------------------------------------------------------------
# engineering_status
# ---------------------------------------------------------------------------


class TestEngineeringStatus:
    def test_engineering_status_pass_no_failures(self):
        result = compute_quality_status(_qg_result(passed=True), _dc())
        assert result["engineering_status"] == "PASS"

    def test_engineering_status_failed_hard_failure(self):
        """Hard engineering failure checks should produce FAILED."""
        qg = _qg_result(
            passed=False,
            fail_count=1,
            checks=[
                {"id": "fund_analysis_no_formal_decision", "status": "FAIL"},
            ],
        )
        result = compute_quality_status(qg, _dc())
        assert result["engineering_status"] == "FAILED"

    def test_engineering_status_failed_broker_execution(self):
        qg = _qg_result(
            passed=False,
            fail_count=1,
            checks=[
                {"id": "no_broker_execution", "status": "FAIL"},
            ],
        )
        result = compute_quality_status(qg, _dc())
        assert result["engineering_status"] == "FAILED"

    def test_engineering_status_pass_missing_data_failure(self):
        """Failures due to missing data should not flag engineering issues."""
        qg = _qg_result(
            passed=False,
            fail_count=1,
            checks=[
                {"id": "missing_nav_data", "status": "FAIL"},
            ],
        )
        result = compute_quality_status(qg, _dc())
        assert result["engineering_status"] == "PASS"

    def test_engineering_status_needs_fix_non_missing_failure(self):
        """Non-missing, non-hard-engineering failure should produce NEEDS_FIX."""
        qg = _qg_result(
            passed=False,
            fail_count=1,
            checks=[
                {"id": "some_other_check", "status": "FAIL"},
            ],
        )
        result = compute_quality_status(qg, _dc())
        assert result["engineering_status"] == "NEEDS_FIX"


# ---------------------------------------------------------------------------
# report_professional_status
# ---------------------------------------------------------------------------


class TestReportProfessionalStatus:
    def test_report_professional_status_professional(self):
        result = compute_quality_status(_qg_result(), _dc(grade="A", score=0.95))
        assert result["report_professional_status"] == "PROFESSIONAL"

    def test_report_professional_status_professional_grade_b(self):
        result = compute_quality_status(_qg_result(), _dc(grade="B", score=0.80))
        assert result["report_professional_status"] == "PROFESSIONAL"

    def test_report_professional_status_limited_by_data(self):
        """Grade C should produce LIMITED_BY_DATA."""
        result = compute_quality_status(_qg_result(), _dc(grade="C", score=0.50))
        assert result["report_professional_status"] == "LIMITED_BY_DATA"

    def test_report_professional_status_limited_by_missing_sections(self):
        """Grade A with missing optional sections should produce LIMITED_BY_DATA."""
        result = compute_quality_status(
            _qg_result(),
            _dc(grade="A", score=0.95, missing_sections=["Fund Profiles"]),
        )
        assert result["report_professional_status"] == "LIMITED_BY_DATA"

    def test_report_professional_status_not_usable(self):
        """Grade D should produce NOT_USABLE."""
        result = compute_quality_status(_qg_result(), _dc(grade="D", score=0.10))
        assert result["report_professional_status"] == "NOT_USABLE"

    def test_report_professional_status_not_usable_core_missing(self):
        """Core missing sections should produce NOT_USABLE even with grade A."""
        result = compute_quality_status(
            _qg_result(),
            _dc(grade="A", score=0.95, critical_missing=["Portfolio Snapshot"]),
        )
        assert result["report_professional_status"] == "NOT_USABLE"


# ---------------------------------------------------------------------------
# required_user_data
# ---------------------------------------------------------------------------


class TestRequiredUserData:
    def test_required_user_data_includes_missing_fields(self):
        """Missing sections should map to required_user_data entries."""
        fa = {
            "artifacts": {
                "factor_snapshot": {
                    "data_quality": {
                        "current_value_missing_count": 2,
                        "cost_basis_missing_count": 1,
                        "units_missing_count": 0,
                        "nav_missing_count": 0,
                    }
                }
            }
        }
        dc = _dc(
            grade="B",
            score=0.70,
            missing_sections=["Fund Profiles", "Nav History"],
        )
        result = compute_quality_status(_qg_result(), dc, fa)
        required = result["required_user_data"]
        assert "current_value" in required
        assert "cost_basis" in required
        assert "fund_profile" in required
        assert "NAV_history" in required

    def test_required_user_data_empty_when_complete(self):
        result = compute_quality_status(_qg_result(), _dc(grade="A", score=0.99))
        assert result["required_user_data"] == []


# ---------------------------------------------------------------------------
# Grade D edge case
# ---------------------------------------------------------------------------


class TestGradeDEdgeCase:
    def test_data_grade_d_not_engineering_failure(self):
        """Grade D alone should NOT make engineering_status=FAILED.

        Grade D is a data completeness issue, not an engineering defect.
        engineering_status should remain PASS when there are no check failures.
        """
        result = compute_quality_status(_qg_result(passed=True), _dc(grade="D", score=0.10))
        assert result["engineering_status"] == "PASS"
        assert result["data_completeness_grade"] == "D"
        assert result["data_readiness_status"] == "INCOMPLETE"
        assert result["report_professional_status"] == "NOT_USABLE"


# ---------------------------------------------------------------------------
# Return structure completeness
# ---------------------------------------------------------------------------


class TestReturnStructure:
    def test_all_keys_present(self):
        result = compute_quality_status(_qg_result(), _dc())
        expected_keys = {
            "pipeline_status",
            "data_readiness_status",
            "engineering_status",
            "report_professional_status",
            "required_user_data",
            "data_completeness_grade",
            "data_completeness_score",
            "quality_gate_passed",
            "quality_gate_fail_count",
            "quality_gate_warn_count",
        }
        assert set(result.keys()) == expected_keys

    def test_none_inputs_use_defaults(self):
        """Passing None for optional args should not crash."""
        result = compute_quality_status(_qg_result(), None, None, None)
        assert result["data_completeness_grade"] == "D"
        assert result["data_completeness_score"] == 0.0
        assert result["required_user_data"] == []

    def test_uncertainty_note_gap_upgrades_engineering(self):
        """If data is incomplete but no uncertainty note, engineering -> NEEDS_FIX."""
        fa = {
            "artifacts": {
                "factor_snapshot": {
                    "data_quality": {
                        "uncertainty_note": None,
                    }
                }
            }
        }
        dc = _dc(grade="C", score=0.50)
        result = compute_quality_status(_qg_result(), dc, fa)
        assert result["engineering_status"] == "NEEDS_FIX"
