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

from scripts.fund_identity_utils import is_valid_fund_code, normalize_fund_name
from src.tools.portfolio.nav_coverage import (
    DOMESTIC_STALE_THRESHOLD_DAYS,
    QDII_STALE_THRESHOLD_DAYS,
    compute_nav_coverage,
    compute_portfolio_nav_coverage,
)
from src.tools.portfolio.trade_date_rules import compute_effective_trade_date


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


def _build_identity_map(identity_data: dict[str, Any] | None) -> tuple[dict[str, str], set[str]]:
    """Build a multi-key mapping from fund_name variants to resolved_fund_code.

    Indexes by fund_name, normalized_name, raw_fund_name, and normalized
    variants.  Only includes entries where resolved_fund_code is a valid
    six-digit code and identity_verification_status is NOT code_name_mismatch.

    Returns:
        Tuple of (name_to_code mapping, set of identity_mismatch fund codes).
    """
    if not identity_data:
        return {}, set()
    entries = identity_data.get("resolutions", identity_data.get("funds", []))
    code_field = "resolved_fund_code" if "resolutions" in identity_data else "resolved_code"
    name_to_code: dict[str, str] = {}
    identity_mismatch_codes: set[str] = set()
    for entry in entries:
        code = entry.get(code_field, "")
        if not is_valid_fund_code(code):
            continue
        # Block identity-mismatch codes from the map
        ivs = entry.get("identity_verification_status", "")
        if ivs == "code_name_mismatch":
            identity_mismatch_codes.add(code)
            continue
        # Index by all available name variants
        for name in (
            entry.get("fund_name"),
            entry.get("normalized_name"),
            entry.get("raw_fund_name"),
            entry.get("raw_reference"),
        ):
            if name:
                name_to_code[name] = code
                norm = normalize_fund_name(name)
                if norm and norm != name:
                    name_to_code[norm] = code
    return name_to_code, identity_mismatch_codes


def reconstruct_portfolio(
    ledger_data: dict[str, Any],
    nav_snapshot: dict[str, Any] | None = None,
    fee_snapshot: dict[str, Any] | None = None,
    as_of_date: date | None = None,
    identity_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct portfolio positions from transaction ledger.

    Returns dict with confirmed_portfolio, projected_portfolio, portfolio_input.
    """
    as_of = as_of_date or date.today()
    nav_by_fund = nav_snapshot.get("nav_by_fund", {}) if nav_snapshot else {}
    fee_schedules = fee_snapshot.get("fee_schedules", {}) if fee_snapshot else {}

    # Build identity map: fund_name -> resolved six-digit fund_code
    identity_map, identity_mismatch_codes = _build_identity_map(identity_data)

    # Group transactions by canonical fund_code
    # If txn has no fund_code but has fund_name that resolves via identity, use resolved code
    fund_txns: dict[str, list[dict[str, Any]]] = {}
    identity_applied_count = 0
    identity_provenance: dict[str, str] = {}  # fund_code -> how it was resolved
    for txn in ledger_data.get("transactions", []):
        fc = txn.get("fund_code")
        fn = txn.get("fund_name")
        nn = txn.get("normalized_name")
        # Apply identity resolution for name-only transactions
        # Try exact fund_name, then normalized_name, then normalized fund_name
        if not fc:
            resolved = None
            if fn and fn in identity_map:
                resolved = identity_map[fn]
            elif nn and nn in identity_map:
                resolved = identity_map[nn]
            elif fn:
                norm = normalize_fund_name(fn)
                if norm and norm in identity_map:
                    resolved = identity_map[norm]
            if resolved:
                fc = resolved
                identity_applied_count += 1
                identity_provenance[fc] = "identity_resolution"
        if fc:
            fund_txns.setdefault(fc, []).append(txn)

    # Process each fund
    confirmed_positions = []
    projected_positions = []
    reconstruction_notes = []
    pending_transactions = []

    for fund_code, txns in sorted(fund_txns.items()):
        # Block valuation for identity-mismatch funds
        if fund_code in identity_mismatch_codes:
            confirmed_positions.append({
                "fund_code": fund_code,
                "units": None,
                "current_value": None,
                "cost_basis": None,
                "average_cost_per_unit": None,
                "latest_nav": None,
                "latest_nav_date": None,
                "latest_nav_stale_days": None,
                "valuation_type": "none",
                "valuation_source": "identity_mismatch_blocked",
                "valuation_quality": "identity_mismatch",
                "nav_coverage_status": "identity_mismatch_blocked",
                "trade_nav_coverage_ratio": 0.0,
                "trade_nav_missing_count": 0,
                "trades_missing_trade_date_nav": 0,
                "is_qdii_like": False,
                "manual_review_required": True,
                "manual_review_reasons": ["identity_mismatch"],
                "manual_review_transaction_count": 0,
                "data_quality": ["identity_mismatch"],
                "buy_count": 0,
                "sell_count": 0,
                "dividends_received": None,
                "fees_paid": None,
                "fee_unknown": False,
                "pending_amount": None,
                "has_manual_review": True,
                "confirmation_sources": [],
                "identity_provenance": None,
                "confidence": "identity_mismatch",
                "holding_source": "transaction_derived",
            })
            reconstruction_notes.append({
                "fund_code": fund_code,
                "note": "valuation blocked: fund code/name mismatch; verify fund_identity_overrides",
            })
            continue

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

        # Units estimation tracking
        units_from_transaction = 0  # count of txns with explicit units field
        units_from_trade_nav = 0    # count of txns where units derived from trade-date NAV
        total_confirmed_txns = 0    # count of buy/sell confirmed txns (excl dividend/fee/conversion/refund)
        manual_review_txn_count = 0
        has_conversion_or_refund_estimated = False  # True when estimated conversion/refund applied

        for txn in sorted(txns, key=lambda t: t.get("trade_date") or "9999-99-99"):
            conf_type = txn.get("confirmation_type", "pending_confirmation")
            action = txn.get("action", "buy")
            amount = txn.get("amount")
            fee_amount = txn.get("fee_amount")
            trade_date = txn.get("trade_date")
            # Use effective_trade_date for NAV lookup if available (15:00 cutoff)
            effective_td = txn.get("effective_trade_date") or trade_date

            if conf_type == "manual_review_required":
                has_manual_review = True
                manual_review_txn_count += 1
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

                    total_confirmed_txns += 1

                    # Check for explicit units/share field in transaction
                    explicit_units = txn.get("units") or txn.get("shares") or txn.get("confirmed_units")
                    if explicit_units is not None:
                        try:
                            units = float(explicit_units)
                            units_from_transaction += 1
                        except (ValueError, TypeError):
                            units = None
                    else:
                        # Get NAV for this date (use effective_trade_date if available)
                        txn_date = _parse_date(effective_td)
                        txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None

                        # Calculate units
                        if txn_nav and net_amount:
                            units = net_amount / txn_nav
                            units_from_trade_nav += 1
                        else:
                            # Do NOT use latest_nav to back-compute historical units
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

                    total_confirmed_txns += 1

                    # Check for explicit units
                    explicit_units = txn.get("units") or txn.get("shares") or txn.get("confirmed_units")
                    if explicit_units is not None:
                        try:
                            units_sold = abs(float(explicit_units))
                            units_from_transaction += 1
                        except (ValueError, TypeError):
                            units_sold = None
                    else:
                        txn_date = _parse_date(effective_td)
                        txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None

                        units_sold = abs(net_amount) / txn_nav if txn_nav and net_amount else None
                        if units_sold is not None:
                            units_from_trade_nav += 1

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
                    # Dividends do not change units, only record cashflow
                    if amount is not None:
                        dividends += amount

                elif action == "fee":
                    if amount is not None:
                        fees_paid += amount

                elif action == "conversion":
                    # Check special_transaction_status for computability
                    special_status = txn.get("special_transaction_status", "manual_review_required")
                    if special_status == "computable":
                        # conversion_in: source fund loses units
                        # conversion_out: target fund gains units
                        conv_direction = txn.get("transaction_type", "")
                        explicit_units = txn.get("units") or txn.get("shares")
                        conv_amount = amount

                        if conv_direction == "conversion_out" and explicit_units is not None:
                            # Target fund gains units
                            try:
                                units = abs(float(explicit_units))
                                confirmed_units += units
                                projected_units += units
                                if conv_amount is not None:
                                    confirmed_cost += conv_amount
                                    projected_cost += conv_amount
                                confirmation_sources.add("conversion_computable")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        elif conv_direction == "conversion_in" and explicit_units is not None:
                            # Source fund loses units
                            try:
                                units_out = abs(float(explicit_units))
                                if confirmed_units >= units_out:
                                    cost_of_out = confirmed_cost * (units_out / confirmed_units) if confirmed_units > 0 else 0
                                    confirmed_units -= units_out
                                    projected_units -= units_out
                                    confirmed_cost -= cost_of_out
                                    projected_cost -= cost_of_out
                                else:
                                    confirmed_units = max(0, confirmed_units - units_out)
                                    projected_units = max(0, projected_units - units_out)
                                confirmation_sources.add("conversion_computable")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        else:
                            # computable but missing direction or units
                            has_manual_review = True
                            manual_review_txn_count += 1
                            reconstruction_notes.append({
                                "fund_code": fund_code,
                                "note": "conversion computable but missing direction/units",
                                "transaction_id": txn.get("transaction_id"),
                            })
                    elif special_status == "estimated":
                        # Estimated conversion: apply with uncertainty flag
                        conv_direction = txn.get("transaction_type", "")
                        explicit_units = txn.get("units") or txn.get("shares")
                        conv_amount = amount

                        if conv_direction == "conversion_out" and explicit_units is not None:
                            try:
                                units = abs(float(explicit_units))
                                confirmed_units += units
                                projected_units += units
                                if conv_amount is not None:
                                    confirmed_cost += conv_amount
                                    projected_cost += conv_amount
                                has_conversion_or_refund_estimated = True
                                confirmation_sources.add("conversion_estimated")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        elif conv_direction == "conversion_in" and explicit_units is not None:
                            try:
                                units_out = abs(float(explicit_units))
                                if confirmed_units >= units_out:
                                    cost_of_out = confirmed_cost * (units_out / confirmed_units) if confirmed_units > 0 else 0
                                    confirmed_units -= units_out
                                    projected_units -= units_out
                                    confirmed_cost -= cost_of_out
                                    projected_cost -= cost_of_out
                                else:
                                    confirmed_units = max(0, confirmed_units - units_out)
                                    projected_units = max(0, projected_units - units_out)
                                has_conversion_or_refund_estimated = True
                                confirmation_sources.add("conversion_estimated")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        else:
                            has_manual_review = True
                            manual_review_txn_count += 1
                            reconstruction_notes.append({
                                "fund_code": fund_code,
                                "note": "conversion estimated but missing direction/units",
                                "transaction_id": txn.get("transaction_id"),
                            })
                    else:
                        # ambiguous or manual_review_required → skip from units
                        has_manual_review = True
                        manual_review_txn_count += 1
                        reconstruction_notes.append({
                            "fund_code": fund_code,
                            "note": "conversion transaction requires manual review",
                            "transaction_id": txn.get("transaction_id"),
                        })

                elif action == "refund":
                    # Check special_transaction_status for computability
                    special_status = txn.get("special_transaction_status", "manual_review_required")
                    if special_status == "computable":
                        # Refund with amount and matching reference → add back units
                        refund_amount = amount
                        refund_units = txn.get("units") or txn.get("shares")
                        if refund_units is not None:
                            try:
                                units_back = abs(float(refund_units))
                                confirmed_units += units_back
                                projected_units += units_back
                                if refund_amount is not None:
                                    confirmed_cost += refund_amount
                                    projected_cost += refund_amount
                                confirmation_sources.add("refund_computable")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        elif refund_amount is not None:
                            # Amount known but units unknown → add to cost only
                            confirmed_cost += refund_amount
                            projected_cost += refund_amount
                            confirmation_sources.add("refund_computable")
                        else:
                            has_manual_review = True
                            manual_review_txn_count += 1
                    elif special_status == "estimated":
                        # Estimated refund: apply with uncertainty
                        refund_amount = amount
                        refund_units = txn.get("units") or txn.get("shares")
                        if refund_units is not None:
                            try:
                                units_back = abs(float(refund_units))
                                confirmed_units += units_back
                                projected_units += units_back
                                if refund_amount is not None:
                                    confirmed_cost += refund_amount
                                    projected_cost += refund_amount
                                has_conversion_or_refund_estimated = True
                                confirmation_sources.add("refund_estimated")
                            except (ValueError, TypeError):
                                has_manual_review = True
                                manual_review_txn_count += 1
                        elif refund_amount is not None:
                            confirmed_cost += refund_amount
                            projected_cost += refund_amount
                            confirmation_sources.add("refund_estimated")
                        else:
                            has_manual_review = True
                            manual_review_txn_count += 1
                    else:
                        # ambiguous or manual_review_required → skip from units
                        has_manual_review = True
                        manual_review_txn_count += 1
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
                    txn_date = _parse_date(effective_td)
                    txn_nav = _get_nav_on_date(nav_records, txn_date) if txn_date else None
                    net_amount = txn.get("net_amount") or amount

                    if txn_nav and net_amount:
                        units = net_amount / txn_nav
                        projected_units += units
                        projected_cost += net_amount
                        projected_buy_count += 1

        # Compute units estimation metadata
        nav_coverage_count = units_from_trade_nav
        nav_missing_count = total_confirmed_txns - units_from_trade_nav - units_from_transaction
        trade_nav_coverage_ratio = (
            round(nav_coverage_count / total_confirmed_txns, 4)
            if total_confirmed_txns > 0 else 0.0
        )

        # Determine units_source
        if units_from_transaction > 0 and nav_missing_count == 0:
            units_source = "transaction_units"
        elif units_from_trade_nav > 0 and nav_missing_count == 0:
            units_source = "trade_date_nav"
        elif units_from_trade_nav > 0 and nav_missing_count > 0:
            units_source = "partial_trade_date_nav"
        else:
            units_source = "unavailable"

        # Determine valuation_type per the state machine:
        #   none: no transactions, no cost, no NAV, no valuation
        #   cashflow_only: has cost_basis but no units or current_value
        #   estimated: has units + latest_nav → current_value = units * latest_nav
        #   valuation: only when broker/confirmed source exists (not in v0.10.5)
        has_units = confirmed_units > 0
        has_cost = confirmed_cost > 0

        if not has_cost and not has_units:
            valuation_type = "none"
            valuation_source = "none"
        elif has_units and latest_nav is not None:
            valuation_type = "estimated"
            valuation_source = "estimated_from_transactions_and_nav"
        elif has_cost:
            valuation_type = "cashflow_only"
            valuation_source = "cashflow_only"
        else:
            # has_units but no latest_nav — can't compute current_value
            valuation_type = "cashflow_only"
            valuation_source = "cashflow_only"

        # Compute current_value ONLY for estimated positions
        confirmed_current_value = _safe_round(confirmed_units * latest_nav) if valuation_type == "estimated" else None

        # Data quality flags for partial coverage
        partial_units_estimated = units_source == "partial_trade_date_nav"
        data_quality_flags = []
        if partial_units_estimated:
            data_quality_flags.append("partial_trade_nav_coverage")
        if has_manual_review:
            data_quality_flags.append("has_manual_review_transactions")
        if has_conversion_or_refund_estimated:
            data_quality_flags.append("conversion_or_refund_estimated")
        # Valuation output hard gate: mark positions where valuation is blocked
        if valuation_type == "cashflow_only":
            data_quality_flags.append("valuation_blocked_cashflow_only")
        if valuation_type == "none" and has_cost:
            data_quality_flags.append("valuation_blocked_no_nav")

        # Fee schedule status
        fund_fee_schedule = fee_schedules.get(fund_code, {})
        fee_provenance = fund_fee_schedule.get("provenance", {}).get("source", "unavailable")
        if fee_provenance == "manual_override":
            fee_schedule_status = "override_provided"
        elif fund_fee_schedule.get("purchase_fee") is not None or fund_fee_schedule.get("redemption_fee_tiers"):
            fee_schedule_status = "available"
        else:
            fee_schedule_status = "unavailable"

        # Check for redemption fee unknown
        redemption_fee_unknown = False
        if fee_schedule_status == "unavailable":
            redemption_fee_unknown = True
            data_quality_flags.append("redemption_fee_unknown")
        elif not fund_fee_schedule.get("redemption_fee_tiers"):
            redemption_fee_unknown = True
            data_quality_flags.append("redemption_fee_unknown")

        # NAV coverage diagnostics
        nav_cov = compute_nav_coverage(
            fund_code=fund_code,
            transactions=txns,
            nav_records=nav_records,
            as_of_date=as_of,
            is_qdii_like=False,  # default; enriched below if profile available
        )
        valuation_quality = nav_cov["valuation_quality"]
        nav_coverage_status = nav_cov["coverage_status"]
        latest_nav_stale_days = nav_cov.get("latest_nav_stale_days")
        is_qdii_like = nav_cov.get("is_qdii_like", False)

        # If latest_nav_stale_days not set by nav_coverage but we have a date, compute it
        if latest_nav_stale_days is None and latest_nav_date:
            nav_date = date.fromisoformat(latest_nav_date)
            stale = (as_of - nav_date).days
            threshold = QDII_STALE_THRESHOLD_DAYS if is_qdii_like else DOMESTIC_STALE_THRESHOLD_DAYS
            if stale > threshold:
                latest_nav_stale_days = stale
                data_quality_flags.append("latest_nav_stale")

        # Manual review reasons
        manual_review_required = has_manual_review
        manual_review_reasons: list[str] = []
        if has_manual_review:
            manual_review_reasons.append("has_manual_review_transactions")
        if nav_cov.get("warnings"):
            for w in nav_cov["warnings"]:
                if "conversion/refund/unknown" in w:
                    manual_review_reasons.append("conversion_refund_unknown_transactions")
                    manual_review_required = True
        if valuation_quality == "manual_review_required":
            manual_review_required = True

        confirmed_avg_cost = _safe_round(confirmed_cost / confirmed_units) if confirmed_units > 0 else None
        confirmed_cost_basis = _safe_round(confirmed_cost)

        # Valuation coverage annotation for partial estimated positions
        # When estimated with partial NAV coverage, mark the ratio explicitly
        valuation_coverage_ratio = None
        if valuation_type == "estimated" and partial_units_estimated:
            valuation_coverage_ratio = trade_nav_coverage_ratio
            data_quality_flags.append(f"valuation_coverage_{trade_nav_coverage_ratio:.0%}")

        confirmed_pos = {
            "fund_code": fund_code,
            "units": _safe_round(confirmed_units, 4) if confirmed_units > 0 else None,
            "units_estimated": _safe_round(confirmed_units, 4) if units_source in ("trade_date_nav", "partial_trade_date_nav") else None,
            "units_source": units_source,
            "current_value": confirmed_current_value,
            "cost_basis": confirmed_cost_basis,
            "average_cost_per_unit": confirmed_avg_cost,
            "latest_nav": latest_nav,
            "latest_nav_date": latest_nav_date,
            "latest_nav_stale_days": latest_nav_stale_days,
            "valuation_type": valuation_type,
            "valuation_source": valuation_source,
            "valuation_quality": valuation_quality,
            "valuation_coverage_ratio": valuation_coverage_ratio,
            "nav_coverage_status": nav_coverage_status,
            "trade_nav_coverage_ratio": trade_nav_coverage_ratio,
            "trade_nav_missing_count": nav_missing_count,
            "trades_missing_trade_date_nav": nav_cov.get("trades_missing_trade_date_nav", 0),
            "is_qdii_like": is_qdii_like,
            "manual_review_required": manual_review_required,
            "manual_review_reasons": manual_review_reasons,
            "manual_review_transaction_count": manual_review_txn_count,
            "data_quality": data_quality_flags,
            "buy_count": confirmed_buy_count,
            "sell_count": confirmed_sell_count,
            "dividends_received": _safe_round(dividends) if dividends > 0 else None,
            "fees_paid": _safe_round(fees_paid) if fees_paid > 0 else None,
            "fee_unknown": fee_unknown,
            "fee_schedule_status": fee_schedule_status,
            "redemption_fee_unknown": redemption_fee_unknown,
            "pending_amount": _safe_round(pending_amount) if pending_amount > 0 else None,
            "has_manual_review": has_manual_review,
            "confirmation_sources": sorted(confirmation_sources),
            "identity_provenance": identity_provenance.get(fund_code),
            "confidence": "evidence_confirmed" if "alipay" in confirmation_sources or "provider" in confirmation_sources else ("rule_confirmed_estimated" if "schedule_rule" in confirmation_sources else "pending"),
            "holding_source": "transaction_derived",
        }
        confirmed_positions.append(confirmed_pos)

        # Build projected position (confirmed + projected additions)
        if valuation_type == "estimated" and latest_nav is not None:
            projected_current_value = _safe_round(projected_units * latest_nav)
        else:
            projected_current_value = None
        projected_cost_basis = _safe_round(projected_cost)

        projected_pos = {
            "fund_code": fund_code,
            "units": _safe_round(projected_units, 4) if projected_units > 0 else None,
            "current_value": projected_current_value,
            "cost_basis": projected_cost_basis,
            "latest_nav": latest_nav,
            "latest_nav_date": latest_nav_date,
            "valuation_type": valuation_type,
            "valuation_source": valuation_source,
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
            "units_estimated": pos.get("units_estimated"),
            "units_source": pos.get("units_source"),
            "cost_basis": pos["cost_basis"],
            "cost_basis_confidence": pos["confidence"] if pos["confidence"] in ("evidence_confirmed", "rule_confirmed_estimated") else "unknown",
            "valuation_type": pos["valuation_type"],
            "valuation_source": pos.get("valuation_source"),
            "holding_source": "transaction_derived",
            "source_notes": f"Reconstructed from {len(pos.get('confirmation_sources', []))} confirmation source(s)",
        }
        if pos.get("trade_nav_coverage_ratio"):
            holding["trade_nav_coverage_ratio"] = pos["trade_nav_coverage_ratio"]
        if pos.get("data_quality"):
            holding["data_quality"] = pos["data_quality"]
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
        if pos.get("units_source") == "partial_trade_date_nav":
            estimated_fields.append(f"{pos['fund_code']}.units_partial_nav")

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
            "valuation_summary": {
                "estimated_count": sum(1 for p in confirmed_positions if p["valuation_type"] == "estimated"),
                "cashflow_only_count": sum(1 for p in confirmed_positions if p["valuation_type"] == "cashflow_only"),
                "none_count": sum(1 for p in confirmed_positions if p["valuation_type"] == "none"),
                "units_estimated_count": sum(1 for p in confirmed_positions if p.get("units_estimated") is not None),
                "partial_nav_coverage_count": sum(1 for p in confirmed_positions if p.get("units_source") == "partial_trade_date_nav"),
                "redemption_fee_unknown_count": sum(1 for p in confirmed_positions if p.get("redemption_fee_unknown")),
            },
        },
        "source_notes": "Auto-reconstructed from Alipay evidence and investment plan schedule rules",
        "transaction_evidence_refs": [t.get("transaction_id") for t in ledger_data.get("transactions", [])[:10]],
        "pending_transaction_count": len(pending_transactions),
    }

    # Portfolio-level NAV coverage summary
    nav_coverage_summary = compute_portfolio_nav_coverage(
        confirmed_positions, as_of_date=as_of,
    )

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
            "valuation_type_counts": {
                "estimated": sum(1 for p in confirmed_positions if p["valuation_type"] == "estimated"),
                "cashflow_only": sum(1 for p in confirmed_positions if p["valuation_type"] == "cashflow_only"),
                "none": sum(1 for p in confirmed_positions if p["valuation_type"] == "none"),
            },
            "nav_coverage_summary": nav_coverage_summary,
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
        "identity_applied_count": identity_applied_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Reconstruct portfolio from transaction ledger")
    parser.add_argument("--ledger", required=True, help="Path to transaction ledger JSON")
    parser.add_argument("--nav-snapshot", default=None, help="Path to NAV snapshot JSON")
    parser.add_argument("--fee-snapshot", default=None, help="Path to fee schedule snapshot JSON")
    parser.add_argument("--fund-identity-resolution", default=None, help="Path to fund identity resolution JSON")
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

    identity_data = None
    if args.fund_identity_resolution:
        with open(args.fund_identity_resolution, encoding="utf-8") as f:
            identity_data = json.load(f)

    as_of_date = date.fromisoformat(args.as_of_date)

    result = reconstruct_portfolio(
        ledger_data=ledger_data,
        nav_snapshot=nav_snapshot,
        fee_snapshot=fee_snapshot,
        as_of_date=as_of_date,
        identity_data=identity_data,
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
