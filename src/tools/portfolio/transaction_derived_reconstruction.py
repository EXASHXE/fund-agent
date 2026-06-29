"""Transaction-derived units reconstruction — M7.9.

Reconstructs fund units (shares) from transaction amounts, trade-date NAV,
fee rules, and transaction semantics. Each lot is tracked with its
reconstruction quality, and position-level quality is computed from
the aggregation of all lots.

Key design:
- Buy: units = net_amount / trade_date_nav (with fee deduction)
- Sell: units deducted from position (explicit or NAV-derived)
- Conversion: split into conversion_out + conversion_in legs
- Refund: matched to original transaction or manual_review_required
- Dividend: cash (no unit change) or reinvestment (units added)
- Quality gate: reconstruction_quality per position, blockers tracked
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from src.tools.portfolio.valuation_source_model import (
    BLOCKER_SEVERITY_BLOCK,
    BLOCKER_SEVERITY_DEGRADE,
    RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED,
    RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_MISSING_FEE,
    RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV,
    RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS,
    RECONSTRUCTION_BLOCKER_QDII_NAV_LAG,
    RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND,
    RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS,
    RECONSTRUCTION_QUALITY_BLOCKED,
    RECONSTRUCTION_QUALITY_CONFIRMED,
    RECONSTRUCTION_QUALITY_ESTIMATED_HIGH,
    RECONSTRUCTION_QUALITY_ESTIMATED_LOW,
    RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM,
    RECONSTRUCTION_QUALITY_PARTIAL,
    can_output_current_value,
    compute_holdings_source,
    compute_profit_source,
    compute_reconstruction_quality,
    compute_valuation_source_from_holdings,
    get_blocker_severity,
)


# ── Amount semantics ────────────────────────────────────────────────────

AMOUNT_SEMANTICS_GROSS = "gross_amount"          # Includes fees
AMOUNT_SEMANTICS_NET = "net_amount"              # After fee deduction
AMOUNT_SEMANTICS_CONFIRMED = "confirmed_amount"  # Platform-confirmed
AMOUNT_SEMANTICS_UNKNOWN = "unknown"             # Cannot determine

VALID_AMOUNT_SEMANTICS = frozenset({
    AMOUNT_SEMANTICS_GROSS,
    AMOUNT_SEMANTICS_NET,
    AMOUNT_SEMANTICS_CONFIRMED,
    AMOUNT_SEMANTICS_UNKNOWN,
})


# ── Fee confidence ──────────────────────────────────────────────────────

FEE_CONFIDENCE_EXPLICIT = "explicit"            # Fee amount in transaction
FEE_CONFIDENCE_SCHEDULE = "schedule_derived"     # From fee schedule
FEE_CONFIDENCE_UNKNOWN = "unknown"               # No fee info

VALID_FEE_CONFIDENCES = frozenset({
    FEE_CONFIDENCE_EXPLICIT,
    FEE_CONFIDENCE_SCHEDULE,
    FEE_CONFIDENCE_UNKNOWN,
})


# ── Lot reconstruction status ───────────────────────────────────────────

LOT_STATUS_CONFIRMED = "confirmed"
LOT_STATUS_ESTIMATED = "estimated"
LOT_STATUS_BLOCKED_MISSING_TRADE_NAV = "blocked_missing_trade_nav"
LOT_STATUS_BLOCKED_MISSING_UNITS = "blocked_missing_units"
LOT_STATUS_BLOCKED_IDENTITY = "blocked_identity"
LOT_STATUS_MANUAL_REVIEW = "manual_review_required"

VALID_LOT_STATUSES = frozenset({
    LOT_STATUS_CONFIRMED,
    LOT_STATUS_ESTIMATED,
    LOT_STATUS_BLOCKED_MISSING_TRADE_NAV,
    LOT_STATUS_BLOCKED_MISSING_UNITS,
    LOT_STATUS_BLOCKED_IDENTITY,
    LOT_STATUS_MANUAL_REVIEW,
})


# ── Special transaction status (M7.9 extended) ─────────────────────────

SPECIAL_STATUS_CONVERSION_VERIFIED = "conversion_verified"
SPECIAL_STATUS_CONVERSION_ESTIMATED = "conversion_estimated"
SPECIAL_STATUS_REFUND_MATCHED = "refund_matched"
SPECIAL_STATUS_REFUND_UNMATCHED = "refund_unmatched"
SPECIAL_STATUS_MANUAL_REVIEW = "manual_review_required"

VALID_SPECIAL_STATUSES = frozenset({
    SPECIAL_STATUS_CONVERSION_VERIFIED,
    SPECIAL_STATUS_CONVERSION_ESTIMATED,
    SPECIAL_STATUS_REFUND_MATCHED,
    SPECIAL_STATUS_REFUND_UNMATCHED,
    SPECIAL_STATUS_MANUAL_REVIEW,
})


# ── Dividend type ───────────────────────────────────────────────────────

DIVIDEND_TYPE_CASH = "cash_dividend"
DIVIDEND_TYPE_REINVEST = "reinvested_dividend"
DIVIDEND_TYPE_UNKNOWN = "dividend_unmodeled"

VALID_DIVIDEND_TYPES = frozenset({
    DIVIDEND_TYPE_CASH,
    DIVIDEND_TYPE_REINVEST,
    DIVIDEND_TYPE_UNKNOWN,
})


def _safe_round(value: float | None, decimals: int = 2) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, decimals)


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


# ── Buy units reconstruction ────────────────────────────────────────────

def reconstruct_buy_units(
    gross_amount: float | None,
    effective_trade_date: date | None,
    trade_date_nav: float | None,
    subscription_fee_rate: float | None = None,
    fee_amount: float | None = None,
    explicit_units: float | None = None,
    amount_semantics: str = AMOUNT_SEMANTICS_UNKNOWN,
) -> dict[str, Any]:
    """Reconstruct units from a buy transaction.

    Args:
        gross_amount: The transaction amount.
        effective_trade_date: The effective trade date for NAV lookup.
        trade_date_nav: NAV on the effective trade date.
        subscription_fee_rate: Fee rate (e.g., 0.0015 for 0.15%).
        fee_amount: Explicit fee amount if known.
        explicit_units: Explicit units/shares from the transaction.
        amount_semantics: What the amount represents.

    Returns:
        Dict with units, lot_reconstruction_status, and metadata.
    """
    result: dict[str, Any] = {
        "units": None,
        "units_source": "unavailable",
        "lot_reconstruction_status": LOT_STATUS_BLOCKED_MISSING_UNITS,
        "amount_semantics": amount_semantics,
        "fee_source": FEE_CONFIDENCE_UNKNOWN,
        "fee_confidence": FEE_CONFIDENCE_UNKNOWN,
        "fee_amount": None,
        "net_amount": None,
        "trade_nav_source": None,
        "rounding_delta_possible": False,
    }

    # Explicit units take priority
    if explicit_units is not None:
        try:
            units = float(explicit_units)
            if units > 0:
                result["units"] = units
                result["units_source"] = "explicit_units"
                result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
                result["net_amount"] = gross_amount
                return result
        except (ValueError, TypeError):
            pass

    # Need amount and NAV to derive units
    if gross_amount is None or gross_amount <= 0:
        return result

    if trade_date_nav is None or trade_date_nav <= 0:
        result["lot_reconstruction_status"] = LOT_STATUS_BLOCKED_MISSING_TRADE_NAV
        result["net_amount"] = gross_amount
        return result

    result["trade_nav_source"] = "trade_date_nav"

    # Compute fee
    computed_fee = 0.0
    if fee_amount is not None and fee_amount > 0:
        computed_fee = fee_amount
        result["fee_source"] = FEE_CONFIDENCE_EXPLICIT
        result["fee_confidence"] = FEE_CONFIDENCE_EXPLICIT
    elif subscription_fee_rate is not None and subscription_fee_rate > 0:
        computed_fee = gross_amount * subscription_fee_rate
        result["fee_source"] = FEE_CONFIDENCE_SCHEDULE
        result["fee_confidence"] = FEE_CONFIDENCE_SCHEDULE
    else:
        result["fee_source"] = FEE_CONFIDENCE_UNKNOWN
        result["fee_confidence"] = FEE_CONFIDENCE_UNKNOWN

    result["fee_amount"] = _safe_round(computed_fee)

    # Compute net amount based on semantics
    if amount_semantics == AMOUNT_SEMANTICS_GROSS:
        net_amount = gross_amount - computed_fee
    elif amount_semantics in (AMOUNT_SEMANTICS_NET, AMOUNT_SEMANTICS_CONFIRMED):
        net_amount = gross_amount
    else:
        # Unknown semantics — conservative: assume gross if fee known, net if fee unknown
        if computed_fee > 0:
            net_amount = gross_amount - computed_fee
        else:
            net_amount = gross_amount  # Assume net (conservative for units)

    result["net_amount"] = _safe_round(net_amount)

    # Compute units
    if net_amount > 0 and trade_date_nav > 0:
        units = net_amount / trade_date_nav
        result["units"] = units
        result["units_source"] = "trade_date_nav_derived"
        result["rounding_delta_possible"] = True

        # Determine lot status based on data quality
        if amount_semantics == AMOUNT_SEMANTICS_UNKNOWN:
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        elif amount_semantics in (AMOUNT_SEMANTICS_NET, AMOUNT_SEMANTICS_CONFIRMED):
            # Net/confirmed amount — fee doesn't affect unit calculation
            result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
        elif result["fee_confidence"] == FEE_CONFIDENCE_UNKNOWN:
            # Gross amount but fee unknown — estimated
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        else:
            result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED

    return result


# ── Sell units reconstruction ───────────────────────────────────────────

def reconstruct_sell_units(
    redemption_amount: float | None,
    redemption_nav: float | None,
    redemption_fee_rate: float | None = None,
    fee_amount: float | None = None,
    explicit_units: float | None = None,
    amount_semantics: str = AMOUNT_SEMANTICS_UNKNOWN,
    current_units: float = 0.0,
) -> dict[str, Any]:
    """Reconstruct units sold from a sell/redemption transaction.

    Args:
        redemption_amount: The redemption amount.
        redemption_nav: NAV on the redemption date.
        redemption_fee_rate: Redemption fee rate.
        fee_amount: Explicit fee amount.
        explicit_units: Explicit units/shares from the transaction.
        amount_semantics: What the amount represents.
        current_units: Current units held (for negative check).

    Returns:
        Dict with units_sold, lot_reconstruction_status, and metadata.
    """
    result: dict[str, Any] = {
        "units_sold": None,
        "units_source": "unavailable",
        "lot_reconstruction_status": LOT_STATUS_BLOCKED_MISSING_UNITS,
        "amount_semantics": amount_semantics,
        "fee_source": FEE_CONFIDENCE_UNKNOWN,
        "fee_confidence": FEE_CONFIDENCE_UNKNOWN,
        "fee_amount": None,
        "gross_amount": None,
        "trade_nav_source": None,
    }

    # Explicit units take priority
    if explicit_units is not None:
        try:
            units_sold = abs(float(explicit_units))
            if units_sold > 0:
                result["units_sold"] = units_sold
                result["units_source"] = "explicit_units"
                result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
                result["gross_amount"] = redemption_amount
                # Check negative
                if units_sold > current_units:
                    result["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW
                    result["negative_units_warning"] = True
                return result
        except (ValueError, TypeError):
            pass

    # Need amount and NAV to derive units
    if redemption_amount is None or redemption_amount <= 0:
        return result

    if redemption_nav is None or redemption_nav <= 0:
        result["lot_reconstruction_status"] = LOT_STATUS_BLOCKED_MISSING_TRADE_NAV
        return result

    result["trade_nav_source"] = "redemption_nav"

    # Compute fee
    computed_fee = 0.0
    if fee_amount is not None and fee_amount > 0:
        computed_fee = fee_amount
        result["fee_source"] = FEE_CONFIDENCE_EXPLICIT
        result["fee_confidence"] = FEE_CONFIDENCE_EXPLICIT
    elif redemption_fee_rate is not None and redemption_fee_rate > 0:
        computed_fee = redemption_amount * redemption_fee_rate
        result["fee_source"] = FEE_CONFIDENCE_SCHEDULE
        result["fee_confidence"] = FEE_CONFIDENCE_SCHEDULE

    result["fee_amount"] = _safe_round(computed_fee)

    # Infer units based on semantics
    if amount_semantics == AMOUNT_SEMANTICS_GROSS:
        # gross_amount = units_sold * nav → units_sold = gross / nav
        units_sold = redemption_amount / redemption_nav
        result["gross_amount"] = redemption_amount
    elif amount_semantics in (AMOUNT_SEMANTICS_NET, AMOUNT_SEMANTICS_CONFIRMED):
        # net_amount = units_sold * nav * (1 - fee_rate) → units_sold = net / (nav * (1 - fee_rate))
        if redemption_fee_rate is not None and redemption_fee_rate > 0:
            units_sold = redemption_amount / (redemption_nav * (1 - redemption_fee_rate))
        else:
            units_sold = redemption_amount / redemption_nav
        result["gross_amount"] = _safe_round(units_sold * redemption_nav)
    else:
        # Unknown — assume net (conservative for units_sold, may overstate)
        units_sold = redemption_amount / redemption_nav
        result["gross_amount"] = _safe_round(units_sold * redemption_nav)

    if units_sold > 0:
        result["units_sold"] = units_sold
        result["units_source"] = "trade_date_nav_derived"

        # Check negative
        if units_sold > current_units:
            result["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW
            result["negative_units_warning"] = True
        elif amount_semantics == AMOUNT_SEMANTICS_UNKNOWN:
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        elif result["fee_confidence"] == FEE_CONFIDENCE_UNKNOWN:
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        else:
            result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED

    return result


# ── Conversion reconstruction ───────────────────────────────────────────

def reconstruct_conversion(
    conversion_amount: float | None = None,
    source_units: float | None = None,
    target_units: float | None = None,
    source_nav: float | None = None,
    target_nav: float | None = None,
    conversion_fee: float | None = None,
    conversion_group_id: str | None = None,
    has_both_legs: bool = False,
) -> dict[str, Any]:
    """Reconstruct a fund conversion (transfer from one fund to another).

    A conversion must be split into two legs:
    - conversion_out: source fund loses units
    - conversion_in: target fund gains units

    Args:
        conversion_amount: The conversion amount.
        source_units: Units leaving source fund.
        target_units: Units entering target fund.
        source_nav: Source fund NAV on conversion date.
        target_nav: Target fund NAV on conversion date.
        conversion_fee: Conversion fee amount.
        conversion_group_id: Link ID for the two legs.
        has_both_legs: Whether both legs are present.

    Returns:
        Dict with conversion_out and conversion_in leg data.
    """
    result: dict[str, Any] = {
        "conversion_out": {
            "units": None,
            "nav": source_nav,
            "fee": None,
            "lot_reconstruction_status": LOT_STATUS_MANUAL_REVIEW,
        },
        "conversion_in": {
            "units": None,
            "nav": target_nav,
            "fee": None,
            "lot_reconstruction_status": LOT_STATUS_MANUAL_REVIEW,
        },
        "conversion_group_id": conversion_group_id,
        "special_transaction_status": SPECIAL_STATUS_MANUAL_REVIEW,
    }

    if not has_both_legs:
        result["special_transaction_status"] = SPECIAL_STATUS_MANUAL_REVIEW
        result["conversion_out"]["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW
        result["conversion_in"]["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW
        return result

    # Process conversion_out (source fund loses units)
    if source_units is not None:
        try:
            out_units = abs(float(source_units))
            result["conversion_out"]["units"] = out_units
            result["conversion_out"]["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
        except (ValueError, TypeError):
            pass
    elif source_nav is not None and conversion_amount is not None and source_nav > 0:
        out_units = conversion_amount / source_nav
        result["conversion_out"]["units"] = out_units
        result["conversion_out"]["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED

    # Process conversion_in (target fund gains units)
    if target_units is not None:
        try:
            in_units = abs(float(target_units))
            result["conversion_in"]["units"] = in_units
            result["conversion_in"]["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
        except (ValueError, TypeError):
            pass
    elif target_nav is not None and conversion_amount is not None and target_nav > 0:
        in_units = conversion_amount / target_nav
        result["conversion_in"]["units"] = in_units
        result["conversion_in"]["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED

    # Conversion fee
    if conversion_fee is not None:
        result["conversion_out"]["fee"] = conversion_fee
    elif conversion_fee is None and source_units is None:
        # Fee missing and units estimated → degrade quality
        pass

    # Determine special status
    out_confirmed = result["conversion_out"]["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED
    in_confirmed = result["conversion_in"]["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED
    out_estimated = result["conversion_out"]["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED
    in_estimated = result["conversion_in"]["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    if out_confirmed and in_confirmed:
        result["special_transaction_status"] = SPECIAL_STATUS_CONVERSION_VERIFIED
    elif out_estimated or in_estimated:
        result["special_transaction_status"] = SPECIAL_STATUS_CONVERSION_ESTIMATED
    else:
        result["special_transaction_status"] = SPECIAL_STATUS_MANUAL_REVIEW

    return result


# ── Refund reconstruction ───────────────────────────────────────────────

def reconstruct_refund(
    refund_amount: float | None = None,
    refund_units: float | None = None,
    matched_original_transaction_id: str | None = None,
) -> dict[str, Any]:
    """Reconstruct a refund transaction.

    Refunds must be matched to the original transaction. Unmatched refunds
    block full reconstruction.

    Args:
        refund_amount: The refund amount.
        refund_units: Units being refunded (if known).
        matched_original_transaction_id: ID of the original transaction.

    Returns:
        Dict with refund reconstruction data.
    """
    result: dict[str, Any] = {
        "units": None,
        "amount": refund_amount,
        "special_transaction_status": SPECIAL_STATUS_REFUND_UNMATCHED,
        "matched_original_transaction_id": matched_original_transaction_id,
        "lot_reconstruction_status": LOT_STATUS_MANUAL_REVIEW,
    }

    if matched_original_transaction_id is None:
        # Unmatched refund → manual review
        result["special_transaction_status"] = SPECIAL_STATUS_REFUND_UNMATCHED
        result["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW
        return result

    # Matched refund
    result["special_transaction_status"] = SPECIAL_STATUS_REFUND_MATCHED

    if refund_units is not None:
        try:
            units = abs(float(refund_units))
            result["units"] = units
            result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
        except (ValueError, TypeError):
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
    elif refund_amount is not None:
        # Amount known but units unknown — partial info
        result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
    else:
        result["lot_reconstruction_status"] = LOT_STATUS_MANUAL_REVIEW

    return result


# ── Dividend handling ───────────────────────────────────────────────────

def reconstruct_dividend(
    dividend_amount: float | None = None,
    dividend_type: str = DIVIDEND_TYPE_UNKNOWN,
    reinvest_nav: float | None = None,
    reinvest_units: float | None = None,
) -> dict[str, Any]:
    """Handle dividend transaction.

    Cash dividends don't change units. Reinvested dividends add units.
    Unknown dividend type degrades quality.

    Args:
        dividend_amount: The dividend amount.
        dividend_type: Cash, reinvested, or unknown.
        reinvest_nav: NAV for reinvestment (if applicable).
        reinvest_units: Explicit reinvestment units.

    Returns:
        Dict with dividend handling data.
    """
    result: dict[str, Any] = {
        "units_change": 0.0,  # No change by default
        "dividend_type": dividend_type,
        "dividend_amount": dividend_amount,
        "lot_reconstruction_status": LOT_STATUS_CONFIRMED,
        "blocker": None,
    }

    if dividend_type == DIVIDEND_TYPE_CASH:
        # Cash dividend — no unit change
        result["units_change"] = 0.0
        result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED

    elif dividend_type == DIVIDEND_TYPE_REINVEST:
        # Reinvested dividend — units increase
        if reinvest_units is not None:
            try:
                units = float(reinvest_units)
                result["units_change"] = units
                result["lot_reconstruction_status"] = LOT_STATUS_CONFIRMED
            except (ValueError, TypeError):
                if reinvest_nav is not None and dividend_amount is not None and reinvest_nav > 0:
                    result["units_change"] = dividend_amount / reinvest_nav
                    result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
                else:
                    result["units_change"] = 0.0
                    result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
                    result["blocker"] = RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED
        elif reinvest_nav is not None and dividend_amount is not None and reinvest_nav > 0:
            result["units_change"] = dividend_amount / reinvest_nav
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        else:
            # Cannot determine reinvestment units
            result["units_change"] = 0.0
            result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
            result["blocker"] = RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED

    else:
        # Unknown dividend type — don't change units, but flag
        result["units_change"] = 0.0
        result["lot_reconstruction_status"] = LOT_STATUS_ESTIMATED
        result["blocker"] = RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED

    return result


# ── Position reconstruction ─────────────────────────────────────────────

def reconstruct_position(
    transactions: list[dict[str, Any]],
    nav_records: list[dict[str, Any]] | None = None,
    fee_schedules: dict[str, Any] | None = None,
    identity_status: str = "",
    latest_nav: float | None = None,
    latest_nav_date: str | None = None,
    as_of_date: date | None = None,
    has_snapshot: bool = False,
) -> dict[str, Any]:
    """Reconstruct a single fund position from its transactions.

    Processes all transactions in order, tracking units, cost, and
    reconstruction quality. Produces position-level output with
    holdings_source, valuation_source, and reconstruction_quality.

    Args:
        transactions: List of transaction dicts for this fund.
        nav_records: NAV records for this fund.
        fee_schedules: Fee schedule data.
        identity_status: Identity verification status.
        latest_nav: Latest NAV as of as_of_date.
        latest_nav_date: Date of latest NAV.
        as_of_date: As-of date for valuation.
        has_snapshot: Whether a holdings snapshot exists.

    Returns:
        Position dict with all reconstruction data.
    """
    as_of = as_of_date  # as_of_date is required — caller must provide it
    nav_recs = nav_records or []
    fee_sched = fee_schedules or {}

    total_units = 0.0
    total_cost = 0.0
    lot_statuses: list[str] = []
    blockers: list[str] = []
    buy_count = 0
    sell_count = 0
    conversion_count = 0
    refund_count = 0
    dividend_count = 0
    dividend_unmodeled_count = 0
    unmatched_refund_count = 0
    manual_review_count = 0
    has_negative_units = False

    for txn in sorted(transactions, key=lambda t: t.get("trade_date") or "9999-99-99"):
        action = txn.get("action", "buy")
        amount = txn.get("amount")
        conf_type = txn.get("confirmation_type", "pending_confirmation")

        if conf_type == "manual_review_required":
            manual_review_count += 1
            continue

        if conf_type not in ("evidence_confirmed", "rule_confirmed"):
            continue

        if action == "buy":
            result = reconstruct_buy_units(
                gross_amount=amount,
                effective_trade_date=_parse_date(txn.get("effective_trade_date")),
                trade_date_nav=_get_nav_on_date(nav_recs, _parse_date(txn.get("effective_trade_date"))),
                subscription_fee_rate=fee_sched.get("subscription_fee_rate"),
                fee_amount=txn.get("fee_amount"),
                explicit_units=txn.get("units") or txn.get("shares") or txn.get("confirmed_units"),
                amount_semantics=txn.get("amount_semantics", AMOUNT_SEMANTICS_UNKNOWN),
            )
            if result["units"] is not None:
                total_units += result["units"]
                total_cost += amount or 0
                buy_count += 1
            elif amount is not None:
                total_cost += amount
                buy_count += 1

            lot_statuses.append(result["lot_reconstruction_status"])

            # Track blockers
            if result["fee_confidence"] == FEE_CONFIDENCE_UNKNOWN and amount is not None:
                if RECONSTRUCTION_BLOCKER_MISSING_FEE not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_MISSING_FEE)
            if result.get("amount_semantics") == AMOUNT_SEMANTICS_UNKNOWN:
                if RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS)

        elif action == "sell":
            result = reconstruct_sell_units(
                redemption_amount=amount,
                redemption_nav=_get_nav_on_date(nav_recs, _parse_date(txn.get("effective_trade_date"))),
                redemption_fee_rate=fee_sched.get("redemption_fee_rate"),
                fee_amount=txn.get("fee_amount"),
                explicit_units=txn.get("units") or txn.get("shares") or txn.get("confirmed_units"),
                amount_semantics=txn.get("amount_semantics", AMOUNT_SEMANTICS_UNKNOWN),
                current_units=total_units,
            )
            if result["units_sold"] is not None:
                units_sold = result["units_sold"]
                if total_units > 0:
                    cost_of_sold = total_cost * (units_sold / total_units) if total_units > 0 else 0
                    total_units -= units_sold
                    total_cost -= cost_of_sold
                else:
                    total_units = max(0, total_units - units_sold)
                sell_count += 1
                if total_units < 0:
                    has_negative_units = True
                    total_units = 0
            elif amount is not None:
                sell_count += 1

            lot_statuses.append(result["lot_reconstruction_status"])

            if result.get("negative_units_warning"):
                if RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS)

        elif action == "conversion":
            conv_result = reconstruct_conversion(
                conversion_amount=amount,
                source_units=txn.get("units") or txn.get("shares"),
                target_units=txn.get("target_units"),
                source_nav=_get_nav_on_date(nav_recs, _parse_date(txn.get("effective_trade_date"))),
                target_nav=txn.get("target_nav"),
                conversion_fee=txn.get("fee_amount"),
                conversion_group_id=txn.get("conversion_group_id"),
                has_both_legs=txn.get("has_both_legs", False),
            )

            conv_direction = txn.get("transaction_type", "")
            special_status = conv_result["special_transaction_status"]

            if conv_direction == "conversion_out" and conv_result["conversion_out"]["units"] is not None:
                total_units += conv_result["conversion_out"]["units"]
                if amount is not None:
                    total_cost += amount
                conversion_count += 1
                lot_statuses.append(conv_result["conversion_out"]["lot_reconstruction_status"])
            elif conv_direction == "conversion_in" and conv_result["conversion_in"]["units"] is not None:
                units_out = conv_result["conversion_in"]["units"]
                if total_units >= units_out:
                    cost_of_out = total_cost * (units_out / total_units) if total_units > 0 else 0
                    total_units -= units_out
                    total_cost -= cost_of_out
                else:
                    total_units = max(0, total_units - units_out)
                conversion_count += 1
                lot_statuses.append(conv_result["conversion_in"]["lot_reconstruction_status"])
            else:
                manual_review_count += 1
                lot_statuses.append(LOT_STATUS_MANUAL_REVIEW)
                if RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED)

            if special_status == SPECIAL_STATUS_CONVERSION_ESTIMATED:
                if RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED)

        elif action == "refund":
            refund_result = reconstruct_refund(
                refund_amount=amount,
                refund_units=txn.get("units") or txn.get("shares"),
                matched_original_transaction_id=txn.get("matched_original_transaction_id"),
            )

            if refund_result["special_transaction_status"] == SPECIAL_STATUS_REFUND_MATCHED:
                if refund_result["units"] is not None:
                    total_units += refund_result["units"]
                    if amount is not None:
                        total_cost += amount
                elif amount is not None:
                    total_cost += amount
                refund_count += 1
            else:
                unmatched_refund_count += 1
                if RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND)

            lot_statuses.append(refund_result["lot_reconstruction_status"])

        elif action == "dividend":
            div_result = reconstruct_dividend(
                dividend_amount=amount,
                dividend_type=txn.get("dividend_type", DIVIDEND_TYPE_UNKNOWN),
                reinvest_nav=_get_nav_on_date(nav_recs, _parse_date(txn.get("effective_trade_date"))),
                reinvest_units=txn.get("reinvest_units"),
            )

            total_units += div_result["units_change"]
            dividend_count += 1

            if div_result.get("blocker") == RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED:
                dividend_unmodeled_count += 1
                if RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED not in blockers:
                    blockers.append(RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED)

            lot_statuses.append(div_result["lot_reconstruction_status"])

    # Identity blockers
    if identity_status in ("code_name_mismatch", "manual_override_unverified",
                           "provider_lookup_failed", "name_only", "invalid_code"):
        if identity_status == "code_name_mismatch":
            if RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED not in blockers:
                blockers.append(RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED)
        else:
            if RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED not in blockers:
                blockers.append(RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED)

    # Compute units coverage
    lots_with_units = sum(1 for s in lot_statuses if s in (LOT_STATUS_CONFIRMED, LOT_STATUS_ESTIMATED))
    total_lots = len(lot_statuses) if lot_statuses else 0
    units_coverage_ratio = lots_with_units / total_lots if total_lots > 0 else 0.0

    # Compute reconstruction quality
    quality = compute_reconstruction_quality(
        lot_statuses=lot_statuses,
        blockers=blockers,
        units_coverage_ratio=units_coverage_ratio,
        identity_status=identity_status,
    )

    # Compute holdings_source
    has_units = total_units > 0
    has_cost = total_cost > 0
    holdings_source = compute_holdings_source(
        has_snapshot=has_snapshot,
        units_coverage_ratio=units_coverage_ratio,
        has_units=has_units,
        has_cost=has_cost,
        blockers=blockers,
    )

    # Compute valuation_source
    valuation_source = compute_valuation_source_from_holdings(
        holdings_source=holdings_source,
        has_units=has_units,
        has_latest_nav=latest_nav is not None,
        has_current_value_from_snapshot=False,
    )

    # Can we output current_value?
    can_value = can_output_current_value(
        identity_status=identity_status,
        total_units=total_units if total_units > 0 else None,
        latest_nav=latest_nav,
        units_coverage_ratio=units_coverage_ratio if total_lots > 0 else None,
        blockers=blockers,
        reconstruction_quality=quality,
    )

    current_value = _safe_round(total_units * latest_nav) if can_value and latest_nav else None

    return {
        "total_units": _safe_round(total_units, 4) if total_units > 0 else None,
        "units_reconstructed_count": lots_with_units,
        "units_blocked_count": total_lots - lots_with_units,
        "units_coverage_ratio": round(units_coverage_ratio, 4) if total_lots > 0 else None,
        "reconstruction_quality": quality,
        "reconstruction_blockers": blockers,
        "holdings_source": holdings_source,
        "valuation_source": valuation_source,
        "current_value": current_value,
        "cost_basis": _safe_round(total_cost),
        "latest_nav": latest_nav,
        "latest_nav_date": latest_nav_date,
        "identity_verification_status": identity_status,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "conversion_count": conversion_count,
        "refund_count": refund_count,
        "dividend_count": dividend_count,
        "dividend_unmodeled_count": dividend_unmodeled_count,
        "unmatched_refund_count": unmatched_refund_count,
        "manual_review_count": manual_review_count,
        "has_negative_units": has_negative_units,
        "lot_statuses": lot_statuses,
    }


def _get_nav_on_date(nav_records: list[dict[str, Any]], target_date: date | None) -> float | None:
    """Get NAV on a specific date from records."""
    if target_date is None:
        return None
    for rec in nav_records:
        d = _parse_date(rec.get("date"))
        nav = rec.get("nav")
        if d == target_date and nav is not None:
            return float(nav)
    return None
