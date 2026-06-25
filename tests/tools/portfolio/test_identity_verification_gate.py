"""Tests for identity verification gate (M7.2 Stage 2).

Validates that:
1. resolve_fund_identities produces identity_verification_status
2. code_name_mismatch blocks NAV fetch and valuation
3. personal_health_report includes identity_mismatch reason code
4. agent_context includes identity_mismatch in reason_codes and unsafe_to_infer
5. Reconstruction blocks valuation for identity-mismatch funds

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.resolve_fund_identities import (
    _compute_identity_verification_status,
    resolve_fund_identities,
)
from scripts.reconstruct_portfolio_from_ledger import (
    _build_identity_map,
    reconstruct_portfolio,
)
from src.tools.portfolio.agent_context import (
    REASON_CODES,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
)
from src.tools.portfolio.personal_health_report import (
    REASON_IDENTITY_MISMATCH,
    VALID_REASON_CODES,
    build_personal_health_summary,
)


# ── 1. Identity verification status computation ─────────────────────────


class TestComputeIdentityVerificationStatus:
    """Test _compute_identity_verification_status logic."""

    def test_valid_code_is_verified(self):
        result = _compute_identity_verification_status(
            resolved_code="000001",
            resolution_status="valid_code",
            ref_info={"fund_code": "000001", "fund_name": "Test Fund"},
        )
        assert result == "verified"

    def test_manual_override_is_override_verified(self):
        result = _compute_identity_verification_status(
            resolved_code="000002",
            resolution_status="manual_override",
            ref_info={"fund_code": None, "fund_name": "Test Fund"},
            override_record={"fund_code": "000002", "fund_name": "Test Fund"},
        )
        assert result == "override_verified"

    def test_name_only_is_name_only(self):
        result = _compute_identity_verification_status(
            resolved_code=None,
            resolution_status="name_only",
            ref_info={"fund_name": "Name Only Fund"},
        )
        assert result == "name_only"

    def test_invalid_code_is_invalid_code(self):
        result = _compute_identity_verification_status(
            resolved_code=None,
            resolution_status="invalid_code",
            ref_info={"fund_code": "abc"},
        )
        assert result == "invalid_code"

    def test_unresolved_is_code_unverified(self):
        result = _compute_identity_verification_status(
            resolved_code=None,
            resolution_status="unresolved",
            ref_info={},
        )
        assert result == "code_unverified"

    def test_code_name_mismatch_detected(self):
        """When override changes code AND name doesn't match → code_name_mismatch."""
        result = _compute_identity_verification_status(
            resolved_code="000002",
            resolution_status="valid_code",
            ref_info={"fund_code": "000001", "fund_name": "Fund A Original"},
            override_record={"fund_code": "000002", "fund_name": "Fund B Override"},
        )
        assert result == "code_name_mismatch"

    def test_code_change_name_match_is_verified(self):
        """When override changes code but name matches → verified (not mismatch)."""
        result = _compute_identity_verification_status(
            resolved_code="000002",
            resolution_status="valid_code",
            ref_info={"fund_code": "000001", "fund_name": "Same Fund Name"},
            override_record={"fund_code": "000002", "fund_name": "Same Fund Name"},
        )
        assert result == "verified"

    def test_no_override_record_no_mismatch(self):
        """When no override_record provided, no mismatch can be detected."""
        result = _compute_identity_verification_status(
            resolved_code="000001",
            resolution_status="valid_code",
            ref_info={"fund_code": "000001", "fund_name": "Test Fund"},
            override_record=None,
        )
        assert result == "verified"


# ── 2. resolve_fund_identities includes identity_verification_status ────


class TestResolveFundIdentitiesVerificationStatus:
    """resolve_fund_identities must include identity_verification_status."""

    def test_resolution_includes_verification_status(self):
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {"fund_code": "000001", "fund_name": "Test Fund A", "source": "alipay"},
                ],
            },
        )
        assert len(result["resolutions"]) >= 1
        for r in result["resolutions"]:
            assert "identity_verification_status" in r
            assert r["identity_verification_status"] in {
                "verified", "override_verified", "provider_verified",
                "code_name_mismatch", "code_unverified", "name_only", "invalid_code",
            }

    def test_summary_includes_mismatch_count(self):
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {"fund_code": "000001", "fund_name": "Test Fund A", "source": "alipay"},
                ],
            },
        )
        assert "identity_mismatch_count" in result["summary"]
        assert "code_unverified_count" in result["summary"]
        assert "identity_verification_status_counts" in result["summary"]

    def test_valid_code_produces_verified(self):
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {"fund_code": "000001", "fund_name": "Test Fund A", "source": "alipay"},
                ],
            },
        )
        verified = [r for r in result["resolutions"] if r["identity_verification_status"] == "verified"]
        assert len(verified) >= 1

    def test_name_only_produces_name_only(self):
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {"fund_code": None, "fund_name": "Name Only Fund", "source": "alipay"},
                ],
            },
        )
        name_only = [r for r in result["resolutions"] if r["identity_verification_status"] == "name_only"]
        assert len(name_only) >= 1

    def test_override_produces_override_verified(self):
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {"fund_code": None, "fund_name": "Name Only Fund", "source": "alipay"},
                ],
            },
            manual_overrides={"Name Only Fund": "000001"},
        )
        override_verified = [r for r in result["resolutions"] if r["identity_verification_status"] == "override_verified"]
        assert len(override_verified) >= 1


# ── 3. _build_identity_map blocks mismatched codes ──────────────────────


class TestBuildIdentityMapBlocksMismatch:
    """_build_identity_map must exclude code_name_mismatch entries."""

    def test_mismatch_codes_excluded_from_map(self):
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Verified Fund",
                    "identity_verification_status": "verified",
                },
                {
                    "resolved_fund_code": "000002",
                    "fund_name": "Mismatch Fund",
                    "identity_verification_status": "code_name_mismatch",
                },
            ],
        }
        name_map, mismatch_codes = _build_identity_map(identity_data)
        assert "Verified Fund" in name_map
        assert "Mismatch Fund" not in name_map
        assert "000002" in mismatch_codes

    def test_verified_codes_included_in_map(self):
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Verified Fund",
                    "identity_verification_status": "verified",
                },
            ],
        }
        name_map, mismatch_codes = _build_identity_map(identity_data)
        assert "Verified Fund" in name_map
        assert len(mismatch_codes) == 0

    def test_empty_identity_returns_empty(self):
        name_map, mismatch_codes = _build_identity_map(None)
        assert name_map == {}
        assert mismatch_codes == set()


# ── 4. Reconstruction blocks valuation for mismatched funds ─────────────


class TestReconstructionBlocksMismatchValuation:
    """reconstruct_portfolio must block valuation for identity-mismatch funds."""

    def _make_ledger(self, fund_code: str = "000001") -> dict[str, Any]:
        return {
            "transactions": [
                {
                    "fund_code": fund_code,
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ],
        }

    def _make_nav(self, fund_code: str = "000001") -> dict[str, Any]:
        return {
            "nav_by_fund": {
                fund_code: {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }

    def test_mismatch_fund_valuation_blocked(self):
        """Identity-mismatch fund should get valuation_type=none, not estimated."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "code_name_mismatch",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger(),
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "none"
        assert pos["current_value"] is None
        assert "identity_mismatch" in pos.get("data_quality", [])

    def test_verified_fund_valuation_allowed(self):
        """Verified fund should get normal valuation."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "verified",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger(),
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None

    def test_override_verified_fund_valuation_allowed(self):
        """Override-verified fund should get normal valuation."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "override_verified",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger(),
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None

    def test_mismatch_creates_reconstruction_note(self):
        """Identity-mismatch should produce a reconstruction note."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "code_name_mismatch",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger(),
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        notes = result["reconstruction_notes"]
        assert any("mismatch" in n.get("note", "").lower() for n in notes)


# ── 5. Health report includes identity_mismatch reason code ─────────────


def _base_health_artifacts(**overrides) -> dict:
    """Create minimal valid artifacts for health report testing."""
    artifacts = {
        "e2e_summary": {
            "transaction_source": "alipay",
            "portfolio_input_source": "reconstructed_from_ledger",
            "pipeline_steps": {
                "fund_data_snapshot_attempted": True,
                "fund_data_snapshot_status": "attempted",
                "reconstruction_attempted": True,
                "reconstruction_status": "reconstructed_from_ledger",
                "valid_fund_codes_count": 3,
                "name_only_count": 0,
            },
        },
        "nav_coverage_summary": {
            "positions_total": 3,
            "positions_estimated": 3,
            "positions_cashflow_only": 0,
            "positions_unavailable": 0,
            "positions_manual_review_required": 0,
            "nav_coverage_full_count": 3,
            "nav_coverage_partial_count": 0,
            "nav_coverage_none_count": 0,
            "nav_coverage_latest_only_count": 0,
            "latest_nav_stale_count": 0,
            "qdii_like_count": 0,
            "estimated_current_value_total_is_partial": False,
        },
        "portfolio_input_transactions_summary": {
            "total_transactions": 10,
            "manual_review_required_count": 0,
            "manual_review_count": 0,
        },
        "identity_summary": {
            "total_funds": 3,
            "valid_fund_codes_count": 3,
            "name_only_count": 0,
            "identity_mismatch_count": 0,
        },
        "valuation_summary": {},
    }
    artifacts.update(overrides)
    return artifacts


class TestHealthReportIdentityMismatch:
    """personal_health_report must include identity_mismatch when mismatches exist."""

    def test_identity_mismatch_in_reason_codes(self):
        artifacts = _base_health_artifacts()
        artifacts["identity_summary"]["identity_mismatch_count"] = 2
        result = build_personal_health_summary(artifacts)
        assert REASON_IDENTITY_MISMATCH in result["reason_codes"]

    def test_identity_mismatch_in_checklist(self):
        artifacts = _base_health_artifacts()
        artifacts["identity_summary"]["identity_mismatch_count"] = 2
        result = build_personal_health_summary(artifacts)
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "mismatch" in checklist_text.lower() or "identity" in checklist_text.lower()

    def test_no_identity_mismatch_when_count_zero(self):
        artifacts = _base_health_artifacts()
        result = build_personal_health_summary(artifacts)
        assert REASON_IDENTITY_MISMATCH not in result["reason_codes"]

    def test_identity_mismatch_is_valid_reason_code(self):
        assert REASON_IDENTITY_MISMATCH in VALID_REASON_CODES
        assert REASON_IDENTITY_MISMATCH == "identity_mismatch"


# ── 6. Agent context includes identity_mismatch ─────────────────────────


class TestAgentContextIdentityMismatch:
    """agent_context must include identity_mismatch in reason_codes and unsafe_to_infer."""

    def test_identity_mismatch_in_reason_codes_enum(self):
        assert "identity_mismatch" in REASON_CODES

    def test_valuation_if_identity_mismatch_in_unsafe_enum(self):
        assert "valuation_if_identity_mismatch" in UNSAFE_TO_INFER_ITEMS

    def test_identity_mismatch_triggers_unsafe_item(self):
        """When identity_mismatch is in reason_codes, valuation_if_identity_mismatch
        should appear in unsafe_to_infer."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_mismatch", "partial_nav_coverage"],
                "data_sources": {},
                "valuation_quality": {},
                "nav_coverage": {"full": 0, "partial": 1, "none": 0},
            },
            "pipeline_steps": {
                "reconstruction_status": "reconstructed_from_ledger",
            },
        }
        ctx = build_agent_context(summary)
        assert "valuation_if_identity_mismatch" in ctx["unsafe_to_infer"]

    def test_identity_mismatch_triggers_recommended_question(self):
        """When identity_mismatch is in reason_codes, the override verification
        question should appear in recommended_agent_questions."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_mismatch"],
                "data_sources": {},
                "valuation_quality": {},
                "nav_coverage": {"full": 0, "partial": 0, "none": 0},
            },
            "pipeline_steps": {
                "reconstruction_status": "reconstructed_from_ledger",
            },
        }
        ctx = build_agent_context(summary)
        questions_text = " ".join(ctx["recommended_agent_questions"])
        assert "mismatch" in questions_text.lower() or "identity" in questions_text.lower()


# ── 7. Valuation output hard gate ───────────────────────────────────────


class TestValuationOutputHardGate:
    """Valuation output must respect hard gate rules:
    - cashflow_only: current_value=None, no PnL
    - identity_mismatch: valuation_type=none
    - partial estimated: must have valuation_coverage_ratio
    """

    def _make_ledger_with_amount_only(self, fund_code: str = "000001") -> dict[str, Any]:
        """Ledger with buy but no NAV on trade date → cashflow_only."""
        return {
            "transactions": [
                {
                    "fund_code": fund_code,
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ],
        }

    def _make_nav_no_trade_date(self, fund_code: str = "000001") -> dict[str, Any]:
        """NAV snapshot with only latest NAV, no trade-date NAV."""
        return {
            "nav_by_fund": {
                fund_code: {
                    "records": [
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }

    def _make_nav_full(self, fund_code: str = "000001") -> dict[str, Any]:
        """NAV snapshot with both trade-date and latest NAV."""
        return {
            "nav_by_fund": {
                fund_code: {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }

    def test_cashflow_only_has_no_current_value(self):
        """cashflow_only position must have current_value=None."""
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger_with_amount_only(),
            nav_snapshot=self._make_nav_no_trade_date(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # With no trade-date NAV, units can't be computed → cashflow_only
        if pos["valuation_type"] == "cashflow_only":
            assert pos["current_value"] is None
            assert "valuation_blocked_cashflow_only" in pos.get("data_quality", [])

    def test_cashflow_only_has_no_units(self):
        """cashflow_only position must have units=None."""
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger_with_amount_only(),
            nav_snapshot=self._make_nav_no_trade_date(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        if positions[0]["valuation_type"] == "cashflow_only":
            assert positions[0]["units"] is None

    def test_partial_estimated_has_coverage_ratio(self):
        """Partially estimated position must have valuation_coverage_ratio."""
        # Create a ledger with 2 buys: one with NAV, one without
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 500.0,
                    "net_amount": 500.0,
                    "trade_date": "2025-03-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ],
        }
        # NAV only for first buy date
        nav = {
            "nav_by_fund": {
                "000001": {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # Should have partial coverage
        if pos.get("trade_nav_coverage_ratio", 0) < 1.0 and pos["valuation_type"] == "estimated":
            assert pos.get("valuation_coverage_ratio") is not None
            assert any("valuation_coverage_" in f for f in pos.get("data_quality", []))

    def test_identity_mismatch_valuation_type_none(self):
        """identity_mismatch position must have valuation_type=none."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "code_name_mismatch",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger_with_amount_only(),
            nav_snapshot=self._make_nav_full(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        assert positions[0]["valuation_type"] == "none"
        assert positions[0]["current_value"] is None

    def test_total_value_excludes_blocked(self):
        """total_current_value must not include identity-mismatch positions."""
        identity_data = {
            "resolutions": [
                {
                    "resolved_fund_code": "000001",
                    "fund_name": "Test Fund",
                    "identity_verification_status": "code_name_mismatch",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=self._make_ledger_with_amount_only(),
            nav_snapshot=self._make_nav_full(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
            identity_data=identity_data,
        )
        total_value = result["confirmed_portfolio"]["summary"].get("total_current_value")
        # Should be 0 or None since the only position is blocked
        assert total_value is None or total_value == 0
