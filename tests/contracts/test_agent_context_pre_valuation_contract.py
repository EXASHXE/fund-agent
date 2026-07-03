"""Contract tests for M7.20 agent context pre-valuation.

Validates that agent context includes pre-valuation readiness information
and that the contract fields are stable.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.pre_valuation_readiness import (
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY,
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED,
    VALUATION_SCOPE_NONE,
    VALUATION_SCOPE_TRANSACTION_DERIVED_FULL,
    VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL,
    PreValuationReadiness,
)


class TestPreValuationReadinessContractFields:
    """PreValuationReadiness must have stable contract fields."""

    def test_all_required_fields_present(self):
        readiness = PreValuationReadiness()
        d = readiness.to_dict()
        required_fields = {
            "identity_verified_all_ledger_funds",
            "current_holding_discovery_available",
            "current_position_confirmed_count",
            "current_position_probable_count",
            "closed_position_probable_count",
            "holdings_snapshot_loaded",
            "holdings_snapshot_reconciled",
            "valuation_ready_position_count",
            "probable_not_in_snapshot_count",
            "snapshot_not_in_probable_count",
            "snapshot_reconciliation_status",
            "transaction_chain_complete",
            "nav_provider_available",
            "valuation_allowed",
            "valuation_scope",
            "blocking_reasons",
            "snapshot_valuation_reconciled",
            "snapshot_valuation_status",
            "valued_position_count",
            "missing_nav_count",
            "nav_date_mismatch_count",
            "amount_mismatch_count",
            "full_portfolio_metrics_allowed",
        }
        assert set(d.keys()) == required_fields

    def test_valuation_scope_valid_values(self):
        """valuation_scope must be one of the allowed values."""
        valid_scopes = {
            VALUATION_SCOPE_NONE,
            VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY,
            VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED,
            VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL,
            VALUATION_SCOPE_TRANSACTION_DERIVED_FULL,
        }
        for scope in valid_scopes:
            readiness = PreValuationReadiness(valuation_scope=scope)
            assert readiness.valuation_scope == scope

    def test_no_private_data_in_readiness(self):
        """PreValuationReadiness must not contain fund codes, names, or amounts."""
        readiness = PreValuationReadiness()
        d = readiness.to_dict()
        d_str = str(d)
        # No 6-digit codes
        import re
        codes = re.findall(r'\b\d{6}\b', d_str)
        assert len(codes) == 0, f"Found potential fund codes in readiness: {codes}"
