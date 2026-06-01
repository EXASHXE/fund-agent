"""Pure transaction analysis tools for personal portfolio — no IO, no network, stdlib only."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from src.schemas.transaction import FundTransaction, PositionCostBasis, TransactionLedgerSummary

TRANSACTION_KEYS = {
    "transaction_id", "fund_code", "fund_name", "action", "type", "date",
    "amount", "shares", "nav", "fee", "notes",
}

VALID_ACTIONS = {"BUY", "SELL", "DIVIDEND", "FEE", "TRANSFER_IN", "TRANSFER_OUT"}


def _parse_date(val: str) -> date | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            continue
    return None


def normalize_fund_transactions(raw: Any) -> tuple[list[FundTransaction], list[str]]:
    """Convert raw list of dicts to FundTransaction objects.

    Accepts a list of dicts, a single dict, or None.  Missing keys default to
    the FundTransaction defaults.  Numeric fields are coerced to float.

    Accepts either "action" or "type" from raw dicts. Normalizes to uppercase.
    Skips invalid transaction rows and returns warnings for each skipped row.

    Returns (transactions, warnings) tuple.
    """
    warnings: list[str] = []
    if raw is None:
        return [], warnings
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return [], warnings

    result: list[FundTransaction] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        try:
            raw_action = str(item.get("action", item.get("type", ""))).upper()
            if raw_action and raw_action not in VALID_ACTIONS:
                warnings.append(
                    f"Row {idx}: invalid action '{raw_action}', expected one of {sorted(VALID_ACTIONS)}. Skipped."
                )
                continue
            result.append(FundTransaction(
                transaction_id=str(item.get("transaction_id", "")),
                fund_code=str(item.get("fund_code", "")),
                fund_name=str(item.get("fund_name", "")),
                action=raw_action,
                date=str(item.get("date", "")),
                amount=float(item.get("amount") or 0),
                shares=float(item["shares"]) if item.get("shares") is not None else None,
                nav=float(item["nav"]) if item.get("nav") is not None else None,
                fee=float(item.get("fee") or 0),
                notes=str(item.get("notes", "")),
            ))
        except (ValueError, TypeError) as exc:
            warnings.append(f"Row {idx}: failed to parse transaction: {exc}. Skipped.")
            continue
    return result, warnings


def calculate_position_cost_basis(
    transactions: list[FundTransaction],
    current_nav_by_fund: dict[str, float] | None = None,
    as_of_date: str = "",
) -> dict[str, PositionCostBasis]:
    """Weighted-average cost basis per fund.

    BUY:     add shares and cost.
    SELL:    reduce shares proportionally (shares and cost reduced by weight).
    TRANSFER_IN:  add shares at given NAV or 0 cost.
    TRANSFER_OUT: subtract shares only (no cost adjustment).
    DIVIDEND / FEE: do not affect cost basis.

    Each transaction is processed in list order.
    """
    current_nav_by_fund = current_nav_by_fund or {}

    shares: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    txn_count: dict[str, int] = defaultdict(int)
    fund_name: dict[str, str] = {}

    for txn in transactions:
        code = txn.fund_code
        if not code:
            continue
        if txn.fund_name:
            fund_name[code] = txn.fund_name
        txn_count[code] += 1

        txn_type = txn.action.upper()

        if txn_type == "BUY":
            s = txn.shares or 0.0
            c = (txn.amount or 0.0) + (txn.fee or 0.0)
            shares[code] += s
            cost[code] += c
        elif txn_type == "SELL":
            s = txn.shares or 0.0
            if s > 0 and shares[code] > 0:
                ratio = s / shares[code]
                if ratio > 1.0:
                    ratio = 1.0
                cost[code] -= cost[code] * ratio
                shares[code] -= s
            else:
                shares[code] -= s
        elif txn_type == "TRANSFER_IN":
            s = txn.shares or 0.0
            nav = txn.nav or 0.0
            c = s * nav
            shares[code] += s
            cost[code] += c
        elif txn_type == "TRANSFER_OUT":
            s = txn.shares or 0.0
            shares[code] -= s
        # DIVIDEND, FEE — no cost-basis effect

    result: dict[str, PositionCostBasis] = {}
    for code in shares:
        total_shares = max(shares[code], 0.0)
        total_cost_value = max(cost[code], 0.0)
        avg_cost = round(total_cost_value / total_shares, 6) if total_shares > 0 else 0.0

        nav_val = current_nav_by_fund.get(code)
        current_value = round(total_shares * nav_val, 2) if nav_val is not None else 0.0
        unrealized_pnl = round(current_value - total_cost_value, 2) if nav_val is not None else 0.0
        unrealized_pnl_pct = (
            round(unrealized_pnl / total_cost_value * 100, 2) if total_cost_value > 0 and nav_val is not None else 0.0
        )

        result[code] = PositionCostBasis(
            fund_code=code,
            total_shares=round(total_shares, 6),
            total_cost=round(total_cost_value, 2),
            average_cost_per_share=avg_cost,
            current_nav=nav_val,
            current_value=current_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            transaction_count=txn_count.get(code, 0),
        )

    return result


def summarize_transaction_ledger(
    transactions: list[FundTransaction],
    current_nav_by_fund: dict[str, float] | None = None,
    as_of_date: str = "",
) -> TransactionLedgerSummary:
    """Aggregate BUY/SELL/DIVIDEND/FEE totals, build cost basis, compute net_flow."""
    total_buys = 0.0
    total_sells = 0.0
    total_dividends = 0.0
    total_fees = 0.0
    buy_count = 0
    sell_count = 0
    cashflow_by_fund: dict[str, float] = defaultdict(float)
    warnings: list[str] = []

    for txn in transactions:
        code = txn.fund_code
        txn_type = txn.action.upper()
        amount = txn.amount or 0.0
        fee = txn.fee or 0.0

        if txn_type == "BUY":
            total_buys += amount
            buy_count += 1
            cashflow_by_fund[code] = cashflow_by_fund.get(code, 0.0) - amount - fee
        elif txn_type == "SELL":
            total_sells += amount
            sell_count += 1
            cashflow_by_fund[code] = cashflow_by_fund.get(code, 0.0) + amount - fee
        elif txn_type == "DIVIDEND":
            total_dividends += amount
            cashflow_by_fund[code] = cashflow_by_fund.get(code, 0.0) + amount
        elif txn_type == "FEE":
            total_fees += amount
            cashflow_by_fund[code] = cashflow_by_fund.get(code, 0.0) - amount

    net_flow = round(total_sells + total_dividends - total_buys - total_fees, 2)

    position_costs = calculate_position_cost_basis(transactions, current_nav_by_fund, as_of_date)

    return TransactionLedgerSummary(
        as_of_date=as_of_date,
        total_buys=round(total_buys, 2),
        total_sells=round(total_sells, 2),
        total_dividends=round(total_dividends, 2),
        total_fees=round(total_fees, 2),
        net_flow=net_flow,
        buy_count=buy_count,
        sell_count=sell_count,
        position_costs=position_costs,
        warnings=warnings,
        cashflow_by_fund=dict(cashflow_by_fund),
    )


def calculate_cashflow_summary(transactions: list[FundTransaction]) -> dict[str, Any]:
    """Compute inflow, outflow, net cashflow, monthly summary, and by-fund breakdown."""
    total_inflow = 0.0
    total_outflow = 0.0
    monthly: defaultdict[str, float] = defaultdict(float)
    by_fund: defaultdict[str, float] = defaultdict(float)

    for txn in transactions:
        code = txn.fund_code
        txn_type = txn.action.upper()
        amount = txn.amount or 0.0
        fee = txn.fee or 0.0

        month_key = ""
        if txn.date:
            parsed = _parse_date(txn.date)
            if parsed:
                month_key = parsed.strftime("%Y-%m")

        if txn_type in ("BUY", "FEE"):
            net_for_txn = amount + fee
            total_outflow += net_for_txn
            by_fund[code] = by_fund.get(code, 0.0) - net_for_txn
            monthly[month_key] = monthly.get(month_key, 0.0) - net_for_txn
        elif txn_type in ("SELL", "DIVIDEND"):
            net_for_txn = amount - fee
            total_inflow += net_for_txn
            by_fund[code] = by_fund.get(code, 0.0) + net_for_txn
            monthly[month_key] = monthly.get(month_key, 0.0) + net_for_txn
        elif txn_type == "TRANSFER_IN":
            total_inflow += amount
            by_fund[code] = by_fund.get(code, 0.0) + amount
            monthly[month_key] = monthly.get(month_key, 0.0) + amount
        elif txn_type == "TRANSFER_OUT":
            total_outflow += amount
            by_fund[code] = by_fund.get(code, 0.0) - amount
            monthly[month_key] = monthly.get(month_key, 0.0) - amount

    return {
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_cashflow": round(total_inflow - total_outflow, 2),
        "monthly_summary": {
            k: round(v, 2) for k, v in sorted(monthly.items())
        },
        "by_fund": {k: round(v, 2) for k, v in by_fund.items()},
    }


def reconcile_portfolio_with_transactions(
    portfolio: Any,
    transaction_summary: TransactionLedgerSummary,
) -> dict[str, Any]:
    """Compare portfolio positions with transaction-derived cost basis.

    Returns dict with matches, mismatches, and warnings.
    """
    portfolio_positions = _extract_portfolio_positions(portfolio)
    cost_positions = transaction_summary.position_costs
    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    warnings: list[str] = []

    seen_codes: set[str] = set()

    for pos in portfolio_positions:
        code = pos.get("fund_code", "")
        if not code:
            continue
        seen_codes.add(code)

        cb = cost_positions.get(code)
        if cb is None:
            mismatches.append({
                "fund_code": code,
                "source": "portfolio_only",
                "portfolio": pos,
                "cost_basis": None,
                "reason": "Fund exists in portfolio but has no transactions",
            })
            continue

        cost_diff = abs((pos.get("total_cost", 0) or 0) - cb.total_cost)
        shares_diff = abs((pos.get("shares", 0) or 0) - cb.total_shares)

        tolerance = 0.01
        if cost_diff <= tolerance and shares_diff <= tolerance:
            matches.append({
                "fund_code": code,
                "portfolio_cost": pos.get("total_cost"),
                "cost_basis_cost": cb.total_cost,
                "portfolio_shares": pos.get("shares"),
                "cost_basis_shares": cb.total_shares,
            })
        else:
            mismatches.append({
                "fund_code": code,
                "source": "mismatch",
                "portfolio": pos,
                "cost_basis": cb.to_dict(),
                "cost_diff": round(cost_diff, 2),
                "shares_diff": round(shares_diff, 6),
            })
            if cost_diff > 0.01:
                warnings.append(
                    f"{code} 持仓成本与交易成本差异 {cost_diff:.2f}"
                )

    for code in cost_positions:
        if code not in seen_codes:
            mismatches.append({
                "fund_code": code,
                "source": "transactions_only",
                "portfolio": None,
                "cost_basis": cost_positions[code].to_dict(),
                "reason": "Transactions exist for fund not in portfolio",
            })

    return {
        "matches": matches,
        "mismatches": mismatches,
        "warnings": warnings,
        "match_count": len(matches),
        "mismatch_count": len(mismatches),
    }


def detect_trading_discipline_flags(
    transactions: list[FundTransaction],
    risk_profile: Any,
    portfolio: Any = None,
    as_of_date: str = "",
) -> list[dict[str, Any]]:
    """Detect trading discipline violations using deterministic rules.

    Checks:
    - Excessive short-term trading (BUY/SELL within 30 days, same fund)
    - Short-term trade budget exceeded
    - Sell below cost (realized loss on sale)
    - Churn detection (repeated BUY/SELL in same fund)
    - Trade amount below minimum
    - DCA interruption
    """
    flags: list[dict[str, Any]] = []

    risk_dict = _to_dict(risk_profile) if risk_profile is not None else {}
    portfolio_dict = _to_dict(portfolio) if portfolio is not None else {}

    short_term_budget_pct = float(risk_dict.get("short_term_trade_budget_pct", 0.1))
    min_trade_amount = float(
        risk_dict.get("min_trade_amount")
        or portfolio_dict.get("min_trade_amount")
        or 0.0
    )

    # ── Pre-compute cost basis for sell-below-cost check ──
    cost_basis_map = {code: cb.total_cost for code, cb in
                      calculate_position_cost_basis(transactions).items()}

    # ── Sort transactions by date ──
    dated = sorted(
        [t for t in transactions if t.date and t.fund_code],
        key=lambda t: t.date,
    )

    # ── Per-fund trade pairs for short-term / churn detection ──
    fund_trades: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in dated:
        parsed = _parse_date(t.date)
        if parsed is None:
            continue
        fund_trades[t.fund_code].append({
            "type": t.action.upper(),
            "date": parsed,
            "amount": t.amount or 0.0,
        })

    short_term_total = 0.0
    churn_funds: dict[str, int] = defaultdict(int)
    short_term_fund_amounts: defaultdict[str, float] = defaultdict(float)

    for code, trades in fund_trades.items():
        for i in range(len(trades)):
            ti = trades[i]
            if ti["type"] != "BUY":
                continue
            for j in range(i + 1, len(trades)):
                tj = trades[j]
                if tj["type"] != "SELL":
                    continue
                delta = (tj["date"] - ti["date"]).days
                if delta <= 30:
                    short_term_total += ti["amount"]
                    short_term_fund_amounts[code] += ti["amount"]
                    flags.append({
                        "type": "short_term_trading",
                        "severity": "high",
                        "message": f"{code}: BUY → SELL in {delta} days, amount {ti['amount']:.2f}",
                        "details": {
                            "fund_code": code,
                            "buy_date": ti["date"].isoformat(),
                            "sell_date": tj["date"].isoformat(),
                            "delta_days": delta,
                            "amount": ti["amount"],
                        },
                    })
                    break  # flag only the first match per buy

        # ── Churn detection: count BUY/SELL pairs ──
        buy_sell_pairs = 0
        i = 0
        trades_sorted = sorted(trades, key=lambda x: x["date"])
        while i < len(trades_sorted) - 1:
            a = trades_sorted[i]
            b = trades_sorted[i + 1]
            if a["type"] == "BUY" and b["type"] == "SELL":
                buy_sell_pairs += 1
                i += 2
            else:
                i += 1
        if buy_sell_pairs >= 3:
            churn_funds[code] = buy_sell_pairs

    # ── Short-term budget exceeded ──
    portfolio_value = portfolio_dict.get("total_value", 0) or 0.0
    budget_limit = portfolio_value * short_term_budget_pct
    if short_term_total > budget_limit and budget_limit > 0:
        flags.append({
            "type": "short_term_budget_exceeded",
            "severity": "high",
            "message": (
                f"短期交易总额 {short_term_total:.2f} 超出预算 {budget_limit:.2f}"
                f"(上限 {short_term_budget_pct:.0%})"
            ),
            "details": {
                "short_term_total": round(short_term_total, 2),
                "budget_limit": round(budget_limit, 2),
                "budget_pct": short_term_budget_pct,
            },
        })

    # ── Churn flags ──
    for code, pair_count in churn_funds.items():
        flags.append({
            "type": "churn_detected",
            "severity": "medium",
            "message": f"{code}: {pair_count} BUY/SELL pairs detected — possible churn",
            "details": {"fund_code": code, "buy_sell_pairs": pair_count},
        })

    # ── Sell below cost ──
    for txn in transactions:
        txn_type = txn.action.upper()
        if txn_type != "SELL":
            continue
        code = txn.fund_code
        if not code:
            continue
        total_cost_for_fund = cost_basis_map.get(code, 0.0)
        if total_cost_for_fund <= 0:
            continue
        # Compare sell proceeds (amount - fee) vs cost allocated to this sale
        sell_proceeds = (txn.amount or 0.0) - (txn.fee or 0.0)
        shares_sold = txn.shares or 0.0
        if shares_sold <= 0:
            continue
        cb_detail = calculate_position_cost_basis(transactions)
        if code in cb_detail:
            cb = cb_detail[code]
            if cb.total_shares > 0:
                cost_allocated = (shares_sold / (cb.total_shares + shares_sold)) * total_cost_for_fund
                if cost_allocated > sell_proceeds:
                    flags.append({
                        "type": "sell_below_cost",
                        "severity": "medium",
                        "message": f"{code}: Sell {shares_sold:.4f} shares proceeds {sell_proceeds:.2f} below allocated cost {cost_allocated:.2f}",
                        "details": {
                            "fund_code": code,
                            "sell_date": txn.date,
                            "shares_sold": shares_sold,
                            "sell_proceeds": round(sell_proceeds, 2),
                            "allocated_cost": round(cost_allocated, 2),
                        },
                    })

    # ── Min trade amount ──
    if min_trade_amount > 0:
        for txn in transactions:
            txn_type = txn.action.upper()
            if txn_type in ("BUY", "SELL"):
                trade_amount = (txn.amount or 0.0) + (txn.fee or 0.0)
                if 0 < trade_amount < min_trade_amount:
                    flags.append({
                        "type": "trade_below_minimum",
                        "severity": "low",
                        "message": f"{txn.fund_code}: {txn_type} amount {trade_amount:.2f} below minimum {min_trade_amount:.2f}",
                        "details": {
                            "fund_code": txn.fund_code,
                            "type": txn_type,
                            "amount": round(trade_amount, 2),
                            "min_trade_amount": min_trade_amount,
                        },
                    })

    # ── DCA interruption ──
    dca_funds = portfolio_dict.get("dca_funds") or portfolio_dict.get("dca") or {}
    if isinstance(dca_funds, list):
        dca_funds = {item.get("fund_code", ""): item for item in dca_funds if item.get("fund_code")}
    if dca_funds:
        now = _parse_date(as_of_date) if as_of_date else date.today()
        for code, dca_cfg in dca_funds.items():
            dca_cfg = _to_dict(dca_cfg)
            interval_days = dca_cfg.get("interval_days") or dca_cfg.get("frequency_days") or 30
            try:
                interval_days = int(interval_days)
            except (TypeError, ValueError):
                interval_days = 30

            fund_buys = [
                _parse_date(t.date)
                for t in transactions
                if t.fund_code == code and t.action.upper() == "BUY" and t.date
            ]
            fund_buys = [d for d in fund_buys if d is not None]
            if fund_buys:
                last_buy = max(fund_buys)
                days_since = (now - last_buy).days
                if days_since > interval_days * 1.5:
                    flags.append({
                        "type": "dca_interruption",
                        "severity": "low",
                        "message": f"{code}: Last DCA buy {days_since} days ago, interval {interval_days} days",
                        "details": {
                            "fund_code": code,
                            "last_buy_date": last_buy.isoformat(),
                            "days_since_last": days_since,
                            "expected_interval": interval_days,
                        },
                    })

    return flags


# ── Internal helpers ──

def _to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return {}


def _extract_portfolio_positions(portfolio: Any) -> list[dict[str, Any]]:
    if portfolio is None:
        return []
    pd = _to_dict(portfolio)
    positions = pd.get("positions") or []
    if isinstance(positions, list):
        return [_to_dict(p) for p in positions]
    return []
