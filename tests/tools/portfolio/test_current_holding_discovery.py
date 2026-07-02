"""Tests for M7.20 current holding discovery.

Validates:
1. buy_only_fund_becomes_current_position_probable
2. buy_then_full_sell_becomes_closed_position_probable
3. conversion_out_becomes_closed_or_manual_review
4. conversion_in_becomes_current_position_probable
5. dividend_only_does_not_create_current_holding
6. refund_only_does_not_create_current_holding
7. identity_unverified_never_current_confirmed
8. holdings_snapshot_upgrades_to_confirmed
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CONVERSION_ONLY,
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_HISTORY_ONLY,
    HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED,
    discover_current_holdings,
    is_current_holding,
)


def _make_transaction(
    fund_code: str = "110011",
    action: str = "buy",
    amount: float = 1000.0,
    trade_date: str = "2026-01-15",
    pending: bool = False,
) -> dict:
    return {
        "fund_code": fund_code,
        "action": action,
        "amount": amount,
        "trade_date": trade_date,
        "source": "alipay",
        "pending": pending,
    }


def _make_identity_resolution(funds: list[dict] | None = None) -> dict:
    if funds is None:
        funds = [{"resolved_fund_code": "110011", "identity_verification_status": "provider_verified"}]
    return {"funds": funds}


class TestBuyOnlyFundBecomesCurrentPositionProbable:
    """Buy-only funds (no sells) → current_position_probable."""

    def test_single_buy(self):
        txns = [_make_transaction(action="buy")]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert len(candidates) == 1
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE
        assert candidates[0].buy_count == 1
        assert candidates[0].sell_count == 0

    def test_multiple_buys(self):
        txns = [
            _make_transaction(action="buy", amount=1000),
            _make_transaction(action="buy", amount=2000),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE
        assert candidates[0].buy_count == 2
        assert candidates[0].gross_buy_amount == 3000.0


class TestBuyThenFullSellBecomesClosedPositionProbable:
    """Buy then sell (near 100%) → closed_position_probable."""

    def test_buy_then_sell(self):
        txns = [
            _make_transaction(action="buy", amount=1000),
            _make_transaction(action="sell", amount=990),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE

    def test_buy_then_exact_sell(self):
        txns = [
            _make_transaction(action="buy", amount=1000),
            _make_transaction(action="sell", amount=1000),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE


class TestConversionOutBecomesClosedOrManualReview:
    """Conversion out → closed or manual_review depending on context."""

    def test_conversion_out_only(self):
        txns = [_make_transaction(action="conversion", amount=500)]
        # Default conversion is conversion_out
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CONVERSION_ONLY

    def test_buy_then_conversion_out(self):
        txns = [
            _make_transaction(action="buy", amount=1000),
            _make_transaction(action="conversion", amount=1000),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        # buy + conversion_out with matching counts → closed
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE


class TestConversionInBecomesCurrentPositionProbable:
    """Conversion in (from another fund) → current_position_probable."""

    def test_conversion_in(self):
        txns = [_make_transaction(action="conversion", amount=500)]
        # Mark as conversion_in via fund_name keyword
        txns[0]["fund_name"] = "某基金 转入"
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE
        assert candidates[0].conversion_in_count == 1


class TestDividendOnlyDoesNotCreateCurrentHolding:
    """Dividend-only transactions → history_only, not current holding."""

    def test_dividend_only(self):
        txns = [_make_transaction(action="dividend", amount=50)]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_HISTORY_ONLY
        assert not is_current_holding(candidates[0].lifecycle_status)

    def test_dividend_count_recorded(self):
        txns = [_make_transaction(action="dividend", amount=50)]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].dividend_count == 1


class TestRefundOnlyDoesNotCreateCurrentHolding:
    """Refund-only transactions → history_only, not current holding."""

    def test_refund_only(self):
        txns = [_make_transaction(action="refund", amount=100)]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_HISTORY_ONLY
        assert not is_current_holding(candidates[0].lifecycle_status)


class TestIdentityUnverifiedNeverCurrentConfirmed:
    """Identity-unverified funds must never reach current_position_confirmed."""

    def test_name_only_cannot_be_confirmed(self):
        txns = [_make_transaction(action="buy")]
        identity = _make_identity_resolution([
            {"resolved_fund_code": "110011", "identity_verification_status": "name_only"},
        ])
        candidates, summary = discover_current_holdings(txns, identity)
        assert candidates[0].lifecycle_status != HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED
        assert "identity_unverified" in candidates[0].blocking_reasons

    def test_name_only_with_snapshot_still_not_confirmed(self):
        txns = [_make_transaction(action="buy")]
        identity = _make_identity_resolution([
            {"resolved_fund_code": "110011", "identity_verification_status": "name_only"},
        ])
        candidates, summary = discover_current_holdings(txns, identity, holdings_snapshot_funds={"110011"})
        assert candidates[0].lifecycle_status != HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED

    def test_provider_verified_with_snapshot_becomes_confirmed(self):
        txns = [_make_transaction(action="buy")]
        identity = _make_identity_resolution([
            {"resolved_fund_code": "110011", "identity_verification_status": "provider_verified"},
        ])
        candidates, summary = discover_current_holdings(txns, identity, holdings_snapshot_funds={"110011"})
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED


class TestHoldingsSnapshotUpgradesToConfirmed:
    """Holdings snapshot can upgrade probable → confirmed."""

    def test_buy_only_without_snapshot_is_probable(self):
        txns = [_make_transaction(action="buy")]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE

    def test_buy_only_with_snapshot_becomes_confirmed(self):
        txns = [_make_transaction(action="buy")]
        candidates, summary = discover_current_holdings(
            txns, _make_identity_resolution(), holdings_snapshot_funds={"110011"},
        )
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED
        assert candidates[0].confidence == "high"

    def test_snapshot_not_matching_fund_stays_probable(self):
        txns = [_make_transaction(action="buy")]
        candidates, summary = discover_current_holdings(
            txns, _make_identity_resolution(), holdings_snapshot_funds={"999999"},
        )
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE


class TestSummaryCounts:
    """Summary counts must match candidate lifecycle statuses."""

    def test_mixed_lifecycle_counts(self):
        txns = [
            _make_transaction(fund_code="110011", action="buy", amount=1000),
            _make_transaction(fund_code="110012", action="buy", amount=1000),
            _make_transaction(fund_code="110012", action="sell", amount=990),
            _make_transaction(fund_code="110013", action="dividend", amount=50),
        ]
        identity = _make_identity_resolution([
            {"resolved_fund_code": "110011", "identity_verification_status": "provider_verified"},
            {"resolved_fund_code": "110012", "identity_verification_status": "provider_verified"},
            {"resolved_fund_code": "110013", "identity_verification_status": "provider_verified"},
        ])
        candidates, summary = discover_current_holdings(txns, identity)
        assert summary.ledger_fund_count == 3
        assert summary.current_position_probable_count == 1  # 110011
        assert summary.closed_position_probable_count == 1  # 110012
        assert summary.history_only_count == 1  # 110013
        assert summary.identity_verified_fund_count == 3

    def test_empty_transactions(self):
        candidates, summary = discover_current_holdings([])
        assert summary.ledger_fund_count == 0
        assert len(candidates) == 0


class TestPartialSell:
    """Partial sell creates manual_review (unclear remaining position)."""

    def test_small_partial_sell(self):
        txns = [
            _make_transaction(action="buy", amount=10000),
            _make_transaction(action="sell", amount=3000),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        # sell_ratio = 0.3 < 0.5, so likely still holding
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE

    def test_medium_partial_sell(self):
        txns = [
            _make_transaction(action="buy", amount=10000),
            _make_transaction(action="sell", amount=6000),
        ]
        candidates, summary = discover_current_holdings(txns, _make_identity_resolution())
        # sell_ratio = 0.6, unclear remaining position
        assert candidates[0].lifecycle_status == HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED
