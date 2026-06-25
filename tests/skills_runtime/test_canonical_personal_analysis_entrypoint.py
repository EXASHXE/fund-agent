"""Tests for the canonical personal analysis entrypoint runtime guard.

When FundAnalysisSkill is called directly with a personal portfolio payload
(without _provenance.source == "personal_run"), a non_canonical_* warning
must be emitted, but the status should NOT be downgraded to PARTIAL.
"""

from __future__ import annotations

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.fund_analysis.skill import _looks_like_personal_portfolio


class TestLooksLikePersonalPortfolio:
    def test_returns_true_when_positions_have_total_cost(self):
        payload = {
            "portfolio": {
                "positions": [
                    {"fund_code": "A", "total_cost": 10000},
                ],
            },
        }
        assert _looks_like_personal_portfolio(payload) is True

    def test_returns_true_when_transactions_present(self):
        payload = {
            "portfolio": {"positions": [{"fund_code": "A"}]},
            "transactions": [{"fund_code": "A", "action": "BUY", "amount": 1000}],
        }
        assert _looks_like_personal_portfolio(payload) is True

    def test_returns_false_when_no_personal_fields(self):
        payload = {
            "portfolio": {
                "positions": [{"fund_code": "A", "current_value": 10000}],
            },
        }
        assert _looks_like_personal_portfolio(payload) is False

    def test_returns_false_when_no_portfolio(self):
        assert _looks_like_personal_portfolio({}) is False

    def test_returns_false_when_empty_positions(self):
        payload = {"portfolio": {"positions": []}}
        assert _looks_like_personal_portfolio(payload) is False


class TestRuntimeGuardWarning:
    def _personal_payload(self):
        return {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 50000.0,
                "positions": [
                    {"fund_code": "A", "fund_name": "Fund A", "current_value": 50000.0, "total_cost": 45000.0},
                ],
            },
            "fund_profiles": {"A": {"fund_code": "A", "fund_type": "equity"}},
            "nav_history": {"A": [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-06-01", "nav": 1.1}]},
        }

    def test_warns_when_called_without_canonical_provenance(self):
        output = FundAnalysisSkill().run(
            SkillInput(
                task_id="test",
                step_id="test",
                skill_name="fund_analysis",
                payload=self._personal_payload(),
            )
        )
        non_canonical = [w for w in output.warnings if w.startswith("non_canonical_")]
        assert len(non_canonical) == 1
        assert "fund-agent-personal-run" in non_canonical[0]

    def test_no_warning_when_canonical_provenance_present(self):
        payload = self._personal_payload()
        payload["_provenance"] = {"source": "personal_run"}
        output = FundAnalysisSkill().run(
            SkillInput(
                task_id="test",
                step_id="test",
                skill_name="fund_analysis",
                payload=payload,
            )
        )
        non_canonical = [w for w in output.warnings if w.startswith("non_canonical_")]
        assert len(non_canonical) == 0

    def test_guard_warning_does_not_downgrade_status(self):
        output = FundAnalysisSkill().run(
            SkillInput(
                task_id="test",
                step_id="test",
                skill_name="fund_analysis",
                payload=self._personal_payload(),
            )
        )
        # The non_canonical_ warning should not cause PARTIAL status
        # (other data quality warnings might, but the guard itself shouldn't)
        assert output.status in ("OK", "PARTIAL")
        # Verify: if only the guard warning exists, status should be OK
        data_warnings = [w for w in output.warnings if not w.startswith("non_canonical_")]
        if not data_warnings:
            assert output.status == "OK"
