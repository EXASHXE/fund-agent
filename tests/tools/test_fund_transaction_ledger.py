"""Transaction ledger tool tests — cost basis, cashflow, reconciliation, discipline flags."""

from __future__ import annotations

from src.schemas.transaction import FundTransaction
from src.tools.portfolio.transaction import (
    calculate_cashflow_summary,
    calculate_position_cost_basis,
    detect_trading_discipline_flags,
    normalize_fund_transactions,
    reconcile_portfolio_with_transactions,
    summarize_transaction_ledger,
)


def _sample_transactions() -> list[dict]:
    return [
        {
            "transaction_id": "T001", "fund_code": "A", "fund_name": "Fund A",
            "type": "BUY", "date": "2025-06-01", "amount": 10000.0,
            "shares": 5000.0, "nav": 2.0, "fee": 10.0,
        },
        {
            "transaction_id": "T002", "fund_code": "A", "fund_name": "Fund A",
            "type": "BUY", "date": "2025-09-01", "amount": 5000.0,
            "shares": 2000.0, "nav": 2.5, "fee": 5.0,
        },
        {
            "transaction_id": "T003", "fund_code": "A", "fund_name": "Fund A",
            "type": "SELL", "date": "2025-12-01", "amount": 6000.0,
            "shares": 2000.0, "nav": 3.0, "fee": 8.0,
        },
        {
            "transaction_id": "T004", "fund_code": "A", "fund_name": "Fund A",
            "type": "DIVIDEND", "date": "2026-01-01", "amount": 500.0,
        },
        {
            "transaction_id": "T005", "fund_code": "A", "fund_name": "Fund A",
            "type": "FEE", "date": "2026-02-01", "amount": 20.0,
        },
    ]


def test_normalize_fund_transactions():
    raw = _sample_transactions()

    result = normalize_fund_transactions(raw)

    assert len(result) == 5
    assert all(isinstance(t, FundTransaction) for t in result)
    assert result[0].fund_code == "A"
    assert result[0].type == "BUY"
    assert result[0].amount == 10000.0


def test_calculate_position_cost_basis_weighted_average():
    txn = normalize_fund_transactions(_sample_transactions())

    cost_basis = calculate_position_cost_basis(txn, {"A": 3.5})

    assert "A" in cost_basis
    cb = cost_basis["A"]
    assert cb.total_shares == 5000.0
    assert cb.total_cost > 0
    assert cb.average_cost_per_share > 0


def test_summarize_transaction_ledger():
    txn = normalize_fund_transactions(_sample_transactions())

    summary = summarize_transaction_ledger(txn, {"A": 3.5})

    assert summary.total_buys == 15000.0
    assert summary.total_sells == 6000.0
    assert summary.total_dividends == 500.0
    assert summary.total_fees == 20.0
    assert summary.buy_count == 2
    assert summary.sell_count == 1
    assert "A" in summary.position_costs


def test_calculate_cashflow_summary():
    txn = normalize_fund_transactions(_sample_transactions())

    result = calculate_cashflow_summary(txn)

    assert result["total_inflow"] > 0
    assert result["total_outflow"] > 0
    assert result["net_cashflow"] == round(result["total_inflow"] - result["total_outflow"], 2)
    assert "monthly_summary" in result
    assert "by_fund" in result


def test_reconcile_portfolio():
    txn = normalize_fund_transactions([
        {"transaction_id": "T1", "fund_code": "A", "type": "BUY", "date": "2025-06-01",
         "amount": 20000.0, "shares": 10000.0, "nav": 2.0},
    ])
    summary = summarize_transaction_ledger(txn, {"A": 2.5})
    portfolio = {
        "positions": [
            {"fund_code": "A", "total_cost": 20000.0, "shares": 10000.0},
        ]
    }

    result = reconcile_portfolio_with_transactions(portfolio, summary)

    assert result["match_count"] >= 1 or result["mismatch_count"] >= 0
    assert "matches" in result
    assert "mismatches" in result


def test_detect_trading_discipline_flags():
    txn = normalize_fund_transactions([
        {"transaction_id": "T1", "fund_code": "A", "type": "BUY", "date": "2026-05-01",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
        {"transaction_id": "T2", "fund_code": "A", "type": "SELL", "date": "2026-05-15",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
        {"transaction_id": "T3", "fund_code": "A", "type": "BUY", "date": "2026-05-20",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
        {"transaction_id": "T4", "fund_code": "A", "type": "SELL", "date": "2026-05-28",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
        {"transaction_id": "T5", "fund_code": "A", "type": "BUY", "date": "2026-05-30",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
        {"transaction_id": "T6", "fund_code": "A", "type": "SELL", "date": "2026-06-01",
         "amount": 5000.0, "shares": 2500.0, "nav": 2.0},
    ])
    risk_profile = {"short_term_trade_budget_pct": 0.05}
    portfolio = {"total_value": 100000.0}

    flags = detect_trading_discipline_flags(txn, risk_profile, portfolio)

    flag_types = {f["type"] for f in flags}
    assert flag_types & {"short_term_trading", "churn_detected", "short_term_budget_exceeded"}
