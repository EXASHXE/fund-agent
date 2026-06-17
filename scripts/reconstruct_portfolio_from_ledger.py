#!/usr/bin/env python3
"""Reconstruct portfolio from transaction ledger.

Outputs:
- confirmed_portfolio.private.json (evidence_confirmed + rule_confirmed)
- projected_portfolio.private.json (confirmed + pending + projected)
- portfolio_input.private.json (format compatible with fund-agent analyze-portfolio)

Calculates units, current_value, cost_basis where possible.
Models subscription fee, redemption fee, unknown fee, dividend, refund, conversion.
No fake precision.

Usage:
    python scripts/reconstruct_portfolio_from_ledger.py \
        --ledger private_data/transaction_ledger.private.json \
        --nav-snapshot private_data/nav_snapshot.private.json \
        --fee-snapshot private_data/fee_schedule_snapshot.private.json \
        --as-of-date 2025-05-19 \
        --output-dir private_data
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any


def _parse_date(val) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _get_latest_nav(nav_records: list[dict[str, Any]], as_of_date: date) -> tuple[float | None, str | None]:
    """Get the latest NAV at or before as_of_date from records."""
    latest_nav = None
    latest_date = None
    for rec in nav_records:
        d = _parse_date(rec.get("date"))
        nav = rec.get("nav")
        if d and nav is not None and d <= as_of_date and (latest_date is None or d > latest_date):
            latest_nav = float(nav)
            latest_date = d
    return latest_nav, latest_date.isoformat() if latest_date else None


def _get_nav_on_date(nav_records: list[dict[str, Any]], target_date: date) -> float | None:
    """Get NAV on a specific date."""
    for rec in nav_records:
        d = _parse_date(rec.get("date"))
        nav = rec.get("nav")
        if d == target_date and nav is not None:
            return float(nav)
    return None


def _safe_round(value: float | None, decimals: int = 2) -> float | None:
    """Round a value, returning None if input is None."""
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, decimals)


def _calculate_units(net_amount: float | None, nav: float | None) -> float | None:
    """Calculate units from net amount and NAV. Returns None if either is missing."""
    if net_amount is None or nav is None or nav == 0:
        return None
    return net_amount / nav


def reconstruct_portfolio(
    ledger_data: dict[str, Any],
    nav_snapshot: dict[str, Any] | None = None,
    fee_snapshot: dict[str, Any] | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Reconstruct portfolio positions from transaction ledger.

    Returns dict with confirmed_portfolio, projected_portfolio, portfolio_input.
    """
    as_of = as_of_date or date.today()
    nav_by_fund = nav_snapshot.get("nav_by_fund", {}) if nav_snapshot else {}

    # Group transactions by fund_code
    fund_txns: dict[str, list[dict[str, Any]]] = {}
    for txn in ledger_data.get("transactions", []):
        fc = txn.get("fund_code")
        if fc:
            fund_txns.setdefault(fc, []).append(txn)

    # Process each fund
    confirmed_positions = []
    projected_positions = []
    reconstruction_notes = []
    pending_transactions = []

    for fund_code, txns in sorted(fund_txns.items()):
        nav_records = nav_by_fund.get(fund_code, {}).get("records", [])
        latest_nav, latest_nav_date = _get_latest_nav(nav_records, as_of)

        # Track position state
        confirmed_units = 0.0
        confirmed_cost = 0.0
        confirmed_buy_count = 0
        confirmed_sell_count = 0
        pending_amount = 0.0
        projected_units = 0.0
        projected_cost = 0.0
        projected_buy_count = 0
        dividends = 0.0
        fees_paid = 0.0
        has_manual_review = False
        confirmation_sources = set()
        fee_unknown = False
        nav_missing_dates = []

        for txn in sorted(txns, key=lambda t: t.get("trade_date") or "9999-99-99"):
            conf_type = txn.get("confirmation_type", "pending_confirmation")
            action = txn.get("action", "buy")
            amount = txn.get("amount")
            fee_amount = txn.get("fee_amount")
            trade_date = txn.get("trade_date")

            if conf_type == "manual_review_required":
                has_manual_review = True
                continue

            # Track confirmation sources for confirmed positions
            if conf_type in ("evidence_confirmed", "rule_confirmed"):
                confirmation_sources.add(txn.get("confirmation_source", "unknown"))

            # Process confirmed transactions (evidence + rule_confirmed)
            if conf_type in ("evidence_confirmed", "rule_confirmed"):
                if action == "buy":
                    net_amount = txn.get("net_amount") or amount
                    if net_amount is None:
                        continue

                    # Get NAV for this date
                    txn_date = _parse_date(trade_date)
                    txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None

                    # Calculate units
                    if txn_nav and net_amount:
                        units = net_amount / txn_nav
                    else:
                        # Try to use latest_nav as fallback for cost tracking
                        units = None
                        if txn_date:
                            nav_missing_dates.append(trade_date)

                    if units is not None:
                        confirmed_units += units
                        projected_units += units
                        confirmed_cost += net_amount
                        projected_cost += net_amount
                        confirmed_buy_count += 1
                        projected_buy_count += 1
                    else:
                        # Amount known but units unknown
                        confirmed_cost += net_amount
                        projected_cost += net_amount
                        confirmed_buy_count += 1
                        projected_buy_count += 1

                    # Track fees
                    if fee_amount is not None:
                        fees_paid += fee_amount
                    elif txn.get("fee_source") == "unknown":
                        fee_unknown = True

                elif action == "sell":
                    net_amount = txn.get("net_amount") or amount
                    if net_amount is None:
                        continue

                    txn_date = _parse_date(trade_date)
                    txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None

                    units_sold = net_amount / txn_nav if txn_nav and net_amount else None

                    if units_sold is not None and confirmed_units > 0:
                        # Pro-rata cost reduction
                        cost_of_sold = confirmed_cost * (units_sold / confirmed_units) if confirmed_units > 0 else 0
                        confirmed_units -= units_sold
                        projected_units -= units_sold
                        confirmed_cost -= cost_of_sold
                        projected_cost -= cost_of_sold
                        confirmed_sell_count += 1
                    elif units_sold is not None:
                        confirmed_units = max(0, confirmed_units - units_sold)
                        projected_units = max(0, projected_units - units_sold)
                        confirmed_sell_count += 1

                    if fee_amount is not None:
                        fees_paid += fee_amount

                elif action == "dividend":
                    if amount is not None:
                        dividends += amount

                elif action == "fee":
                    if amount is not None:
                        fees_paid += amount

                elif action == "conversion":
                    # Conversion is ambiguous -> manual review
                    has_manual_review = True
                    reconstruction_notes.append({
                        "fund_code": fund_code,
                        "note": "conversion transaction requires manual review",
                        "transaction_id": txn.get("transaction_id"),
                    })

                elif action == "refund":
                    # Refund is ambiguous -> manual review
                    has_manual_review = True
                    reconstruction_notes.append({
                        "fund_code": fund_code,
                        "note": "refund transaction requires manual review",
                        "transaction_id": txn.get("transaction_id"),
                    })

            # Process pending transactions
            elif conf_type == "pending_confirmation":
                if action == "buy" and amount is not None:
                    pending_amount += amount
                    pending_transactions.append({
                        "fund_code": fund_code,
                        "amount": amount,
                        "scheduled_date": trade_date,
                        "confirmation_type": conf_type,
                        "confirmation_source": txn.get("confirmation_source"),
                    })

            # Process projected transactions
            elif conf_type == "projected" and action == "buy" and amount is not None:
                    # Add to projected but not to confirmed
                    txn_date = _parse_date(trade_date)
                    txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None
                    net_amount = txn.get("net_amount") or amount

                    if txn_nav and net_amount:
                        units = net_amount / txn_nav
                        projected_units += units
                        projected_cost += net_amount
                        projected_buy_count += 1

        # Build confirmed position
        confirmed_current_value = _safe_round(confirmed_units * latest_nav) if latest_nav and confirmed_units > 0 else None
        confirmed_avg_cost = _safe_round(confirmed_cost / confirmed_units) if confirmed_units > 0 else None
        confirmed_cost_basis = _safe_round(confirmed_cost)

        confirmed_pos = {
            "fund_code": fund_code,
            "units": _safe_round(confirmed_units, 4) if confirmed_units > 0 else None,
            "current_value": confirmed_current_value,
            "cost_basis": confirmed_cost_basis,
            "average_cost_per_unit": confirmed_avg_cost,
            "latest_nav": latest_nav,
            "latest_nav_date": latest_nav_date,
            "buy_count": confirmed_buy_count,
            "sell_count": confirmed_sell_count,
            "dividends_received": _safe_round(dividends) if dividends > 0 else None,
            "fees_paid": _safe_round(fees_paid) if fees_paid > 0 else None,
            "fee_unknown": fee_unknown,
            "pending_amount": _safe_round(pending_amount) if pending_amount > 0 else None,
            "has_manual_review": has_manual_review,
            "confirmation_sources": sorted(confirmation_sources),
            "confidence": "evidence_confirmed" if "alipay" in confirmation_sources or "provider" in confirmation_sources else ("rule_confirmed_estimated" if "schedule_rule" in confirmation_sources else "pending"),
            "holding_source": "transaction_derived",
        }
        confirmed_positions.append(confirmed_pos)

        # Build projected position (confirmed + projected additions)
        projected_current_value = _safe_round(projected_units * latest_nav) if latest_nav and projected_units > 0 else None
        projected_cost_basis = _safe_round(projected_cost)

        projected_pos = {
            "fund_code": fund_code,
            "units": _safe_round(projected_units, 4) if projected_units > 0 else None,
            "current_value": projected_current_value,
            "cost_basis": projected_cost_basis,
            "latest_nav": latest_nav,
            "latest_nav_date": latest_nav_date,
            "pending_amount": _safe_round(pending_amount) if pending_amount > 0 else None,
            "projected_buy_count": projected_buy_count,
            "confidence": "projected",
            "holding_source": "transaction_derived",
        }
        projected_positions.append(projected_pos)

    # Build portfolio_input compatible with fund-agent
    portfolio_input_holdings = []
    for pos in confirmed_positions:
        holding = {
            "fund_code": pos["fund_code"],
            "current_value": pos["current_value"],
            "units": pos["units"],
            "cost_basis": pos["cost_basis"],
            "cost_basis_confidence": pos["confidence"] if pos["confidence"] in ("evidence_confirmed", "rule_confirmed_estimated") else "unknown",
            "holding_source": "transaction_derived",
            "source_notes": f"Reconstructed from {len(pos.get('confirmation_sources', []))} confirmation source(s)",
        }
        if pos.get("pending_amount"):
            holding["pending_transaction_count"] = 1
        portfolio_input_holdings.append(holding)

    total_value = sum(h["current_value"] for h in portfolio_input_holdings if h["current_value"] is not None)

    # Data quality
    missing_fields = []
    estimated_fields = []
    for pos in confirmed_positions:
        if pos["units"] is None:
            missing_fields.append(f"{pos['fund_code']}.units")
        if pos["current_value"] is None:
            missing_fields.append(f"{pos['fund_code']}.current_value")
        if pos["cost_basis"] is None:
            missing_fields.append(f"{pos['fund_code']}.cost_basis")
        if pos["fee_unknown"]:
            estimated_fields.append(f"{pos['fund_code']}.fee")
        if pos.get("has_manual_review"):
            estimated_fields.append(f"{pos['fund_code']}.manual_review_items")

    portfolio_input = {
        "schema_version": "fund_portfolio_input.v1",
        "as_of_date": as_of.isoformat(),
        "holdings": portfolio_input_holdings,
        "data_quality": {
            "missing_fields": missing_fields,
            "estimated_fields": estimated_fields,
            "fund_code_missing": any(h["fund_code"] is None for h in portfolio_input_holdings),
            "units_missing": any(h["units"] is None for h in portfolio_input_holdings),
            "nav_missing": any(pos.get("latest_nav") is None for pos in confirmed_positions),
            "cost_basis_partial": any(h["cost_basis"] is None for h in portfolio_input_holdings if h["cost_basis_confidence"] != "evidence_confirmed"),
            "transaction_history_incomplete": len(pending_transactions) > 0,
            "data_source_notes": ["Portfolio reconstructed from transaction ledger"],
        },
        "source_notes": "Auto-reconstructed from Alipay evidence and investment plan schedule rules",
        "transaction_evidence_refs": [t.get("transaction_id") for t in ledger_data.get("transactions", [])[:10]],
        "pending_transaction_count": len(pending_transactions),
    }

    confirmed_portfolio = {
        "schema_version": "confirmed_portfolio.v1",
        "as_of_date": as_of.isoformat(),
        "positions": confirmed_positions,
        "summary": {
            "total_positions": len(confirmed_positions),
            "total_current_value": _safe_round(total_value),
            "evidence_confirmed_count": sum(1 for p in confirmed_positions if "alipay" in p.get("confirmation_sources", []) or "provider" in p.get("confirmation_sources", [])),
            "rule_confirmed_count": sum(1 for p in confirmed_positions if "schedule_rule" in p.get("confirmation_sources", []) and "alipay" not in p.get("confirmation_sources", [])),
            "has_pending": any(p.get("pending_amount") for p in confirmed_positions),
            "has_manual_review": any(p.get("has_manual_review") for p in confirmed_positions),
        },
    }

    projected_portfolio = {
        "schema_version": "projected_portfolio.v1",
        "as_of_date": as_of.isoformat(),
        "positions": projected_positions,
        "pending_transactions": pending_transactions,
        "summary": {
            "total_positions": len(projected_positions),
            "total_projected_value": _safe_round(sum(p.get("current_value", 0) or 0 for p in projected_positions)),
            "total_pending_amount": _safe_round(sum(p.get("pending_amount", 0) or 0 for p in projected_positions)),
        },
    }

    return {
        "confirmed_portfolio": confirmed_portfolio,
        "projected_portfolio": projected_portfolio,
        "portfolio_input": portfolio_input,
        "reconstruction_notes": reconstruction_notes,
    }


def main():
    parser = argparse.ArgumentParser(description="Reconstruct portfolio from transaction ledger")
    parser.add_argument("--ledger", required=True, help="Path to transaction ledger JSON")
    parser.add_argument("--nav-snapshot", default=None, help="Path to NAV snapshot JSON")
    parser.add_argument("--fee-snapshot", default=None, help="Path to fee schedule snapshot JSON")
    parser.add_argument("--as-of-date", required=True, help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", required=True, help="Output directory for portfolio files")
    args = parser.parse_args()

    with open(args.ledger, encoding="utf-8") as f:
        ledger_data = json.load(f)

    nav_snapshot = None
    if args.nav_snapshot:
        with open(args.nav_snapshot, encoding="utf-8") as f:
            nav_snapshot = json.load(f)

    fee_snapshot = None
    if args.fee_snapshot:
        with open(args.fee_snapshot, encoding="utf-8") as f:
            fee_snapshot = json.load(f)

    as_of_date = date.fromisoformat(args.as_of_date)

    result = reconstruct_portfolio(
        ledger_data=ledger_data,
        nav_snapshot=nav_snapshot,
        fee_snapshot=fee_snapshot,
        as_of_date=as_of_date,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, data in [
        ("confirmed_portfolio.private.json", result["confirmed_portfolio"]),
        ("projected_portfolio.private.json", result["projected_portfolio"]),
        ("portfolio_input.private.json", result["portfolio_input"]),
    ]:
        out_path = output_dir / name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Wrote {out_path}")

    # Print summary
    cp = result["confirmed_portfolio"]
    pp = result["projected_portfolio"]
    print(f"\nConfirmed: {cp['summary']['total_positions']} positions, value={cp['summary'].get('total_current_value')}")
    print(f"Projected: {pp['summary']['total_positions']} positions, pending={pp['summary'].get('total_pending_amount')}")


if __name__ == "__main__":
    main()
