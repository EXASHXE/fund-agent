"""Tests for transaction source routing (decide_transaction_source).

Verifies strict routing semantics for auto/alipay/portfolio_input modes.
"""
from __future__ import annotations

import pytest

# Import from the E2E script — requires REPO_ROOT on sys.path
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.fund_agent_e2e import TransactionSourceDecision, decide_transaction_source


# ── auto mode ──────────────────────────────────────────────────────────


class TestAutoMode:
    def test_alipay_precedence_when_both_exist(self):
        """auto: Alipay CSV takes precedence over portfolio_input.transactions."""
        d = decide_transaction_source("auto", True, True, 5)
        assert d.source == "alipay"
        assert d.use_alipay is True
        assert d.use_portfolio_input_transactions is False

    def test_portfolio_input_fallback_when_no_alipay(self):
        """auto: falls back to portfolio_input.transactions when no Alipay CSV."""
        d = decide_transaction_source("auto", False, True, 5)
        assert d.source == "portfolio_input.transactions"
        assert d.use_portfolio_input_transactions is True
        assert d.use_alipay is False

    def test_no_sources(self):
        """auto: error when neither source available."""
        d = decide_transaction_source("auto", False, False, 0)
        assert d.source == "none"
        assert d.error is not None
        assert d.use_alipay is False
        assert d.use_portfolio_input_transactions is False

    def test_portfolio_input_exists_but_zero_transactions(self):
        """auto: portfolio_input file exists but no transactions → no fallback."""
        d = decide_transaction_source("auto", False, True, 0)
        assert d.source == "none"
        assert d.error is not None

    def test_alipay_only_alipay_exists(self):
        """auto: Alipay CSV exists, no portfolio_input."""
        d = decide_transaction_source("auto", True, False, 0)
        assert d.source == "alipay"
        assert d.use_alipay is True


# ── alipay mode ────────────────────────────────────────────────────────


class TestAlipayMode:
    def test_alipay_available(self):
        """explicit alipay: uses Alipay when available."""
        d = decide_transaction_source("alipay", True, True, 5)
        assert d.source == "alipay"
        assert d.use_alipay is True
        assert d.use_portfolio_input_transactions is False

    def test_alipay_missing_does_not_fallback(self):
        """explicit alipay: does NOT fallback to portfolio_input when CSV missing."""
        d = decide_transaction_source("alipay", False, True, 5)
        assert d.source == "none"
        assert d.error is not None
        assert "no Alipay CSV" in d.error
        assert d.use_alipay is False
        assert d.use_portfolio_input_transactions is False

    def test_alipay_missing_no_portfolio_input(self):
        """explicit alipay: error when CSV missing, even without portfolio_input."""
        d = decide_transaction_source("alipay", False, False, 0)
        assert d.source == "none"
        assert d.error is not None


# ── portfolio_input mode ──────────────────────────────────────────────


class TestPortfolioInputMode:
    def test_portfolio_input_available(self):
        """explicit portfolio_input: uses portfolio_input.transactions."""
        d = decide_transaction_source("portfolio_input", True, True, 5)
        assert d.source == "portfolio_input.transactions"
        assert d.use_portfolio_input_transactions is True
        assert d.use_alipay is False

    def test_overrides_alipay(self):
        """explicit portfolio_input: ignores Alipay CSV even when present."""
        d = decide_transaction_source("portfolio_input", True, True, 5)
        assert d.use_alipay is False
        assert d.use_portfolio_input_transactions is True

    def test_missing_does_not_fallback_to_alipay(self):
        """explicit portfolio_input: does NOT fallback to Alipay when transactions missing."""
        d = decide_transaction_source("portfolio_input", True, True, 0)
        assert d.source == "none"
        assert d.error is not None
        assert "no portfolio_input.transactions" in d.error
        assert d.use_alipay is False
        assert d.use_portfolio_input_transactions is False

    def test_no_portfolio_input_file(self):
        """explicit portfolio_input: error when no portfolio_input file."""
        d = decide_transaction_source("portfolio_input", True, False, 0)
        assert d.source == "none"
        assert d.error is not None


# ── Decision dataclass ────────────────────────────────────────────────


class TestTransactionSourceDecision:
    def test_decision_fields(self):
        d = TransactionSourceDecision(
            source="alipay",
            reason="test",
            use_alipay=True,
        )
        assert d.source == "alipay"
        assert d.reason == "test"
        assert d.use_alipay is True
        assert d.error is None
        assert d.warning is None

    def test_decision_with_error(self):
        d = TransactionSourceDecision(
            source="none",
            reason="test",
            error="something missing",
        )
        assert d.source == "none"
        assert d.error == "something missing"
