"""Portfolio input transactions → ledger adapter.

Converts transactions from portfolio_input.private.json into the standard
ledger format used by build_transaction_ledger.py and
reconstruct_portfolio_from_ledger.py.

No network calls, no private data in logs. Counts-only diagnostics.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.fund_identity_utils import is_valid_fund_code, normalize_fund_name

# Valid transaction types and their mapping to ledger action
TRANSACTION_TYPE_MAP: dict[str, str] = {
    "buy": "buy",
    "sell": "sell",
    "dividend": "dividend",
    "fee": "fee",
    "conversion_in": "conversion",
    "conversion_out": "conversion",
    "refund": "refund",
    "unknown": "unknown",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _determine_special_transaction_status(
    action: str,
    raw: Mapping[str, Any],
) -> str:
    """Determine special_transaction_status for conversion/refund transactions.

    Returns one of: computable, estimated, ambiguous, manual_review_required.
    """
    if action == "conversion":
        # A conversion is computable if we have both source and target fund info
        has_source = bool(raw.get("source_fund_code") or raw.get("from_fund_code"))
        has_target = bool(raw.get("target_fund_code") or raw.get("to_fund_code"))
        has_units = raw.get("units") is not None
        has_nav = raw.get("nav") is not None

        if has_source and has_target and has_units and has_nav:
            return "computable"
        if (has_source or has_target) and (has_units or has_nav):
            return "estimated"
        if has_source or has_target:
            return "ambiguous"
        return "manual_review_required"

    if action == "refund":
        # A refund is computable if we have the amount and matching reference
        has_amount = raw.get("amount") is not None
        has_ref = bool(raw.get("refund_reference") or raw.get("original_transaction_id"))
        has_units = raw.get("units") is not None

        if has_amount and has_ref and has_units:
            return "computable"
        if has_amount and has_ref:
            return "estimated"
        if has_amount:
            return "ambiguous"
        return "manual_review_required"

    return "manual_review_required"


def load_portfolio_input_transactions(path: Path) -> list[dict[str, Any]]:
    """Load transactions from a portfolio_input JSON file.

    Returns the transactions array, or empty list if not present.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    txns = data.get("transactions", [])
    if not isinstance(txns, list):
        return []
    return txns


def normalize_portfolio_input_transaction(
    raw: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    """Normalize a single portfolio_input transaction to ledger format.

    Returns a dict with standard ledger fields plus a 'warnings' list.
    """
    warnings: list[str] = []

    # Required fields
    trade_date = str(raw.get("trade_date", ""))
    if not DATE_RE.match(trade_date):
        warnings.append(f"transaction index {index}: invalid or missing trade_date")

    raw_type = str(raw.get("transaction_type", "")).lower()
    action = TRANSACTION_TYPE_MAP.get(raw_type)
    if action is None:
        action = "unknown"
        warnings.append(f"transaction index {index}: unknown transaction_type")

    amount = raw.get("amount")
    if not isinstance(amount, (int, float)):
        warnings.append(f"transaction index {index}: missing or non-numeric amount")

    # Fund identity
    fund_code = raw.get("fund_code")
    if fund_code is not None:
        fund_code = str(fund_code)
        if not fund_code:
            # Empty string means identity not yet resolved — not an error
            fund_code = None
        elif not is_valid_fund_code(fund_code):
            warnings.append(f"transaction index {index}: fund_code is not 6 digits")
            fund_code = None

    fund_name = raw.get("fund_name")
    if fund_name is not None:
        fund_name = str(fund_name)

    normalized_name = normalize_fund_name(fund_name) if fund_name else None

    # Optional fields
    units = raw.get("units")
    nav = raw.get("nav")

    # Build ledger entry
    entry: dict[str, Any] = {
        "transaction_id": f"pi_txn_{index:06d}",
        "source": "portfolio_input.transactions",
        "fund_code": fund_code,
        "fund_name": fund_name,
        "normalized_name": normalized_name,
        "trade_date": trade_date,
        "action": action,
        "amount": abs(float(amount)) if isinstance(amount, (int, float)) else None,
        "confirmation_type": "user_provided_private_input",
        "confirmation_source": "portfolio_input_transactions",
        "confidence": "user_provided",
    }

    if units is not None and isinstance(units, (int, float)):
        entry["units"] = float(units)
        entry["shares"] = float(units)

    if nav is not None and isinstance(nav, (int, float)):
        entry["nav"] = float(nav)

    # Mark ambiguous portfolio effects and manual review
    manual_review_reasons: list[str] = []
    if action in ("conversion", "refund"):
        entry["ambiguous_portfolio_effect"] = True
        # Determine special_transaction_status based on available data
        special_status = _determine_special_transaction_status(action, raw)
        entry["special_transaction_status"] = special_status
        if special_status == "manual_review_required":
            manual_review_reasons.append(f"ambiguous_portfolio_effect: {action}")
        elif special_status == "ambiguous":
            manual_review_reasons.append(f"insufficient_data_for_{action}_computation")
        # computable/estimated: no manual review needed for the action itself
    if action == "unknown":
        manual_review_reasons.append("unknown_transaction_type")

    # Fee/dividend do not change units — mark for clarity
    if action == "fee":
        entry["fee_transaction"] = True
    if action == "dividend":
        entry["dividend_transaction"] = True

    entry["manual_review_required"] = bool(manual_review_reasons) or bool(warnings)
    if manual_review_reasons:
        entry["manual_review_reasons"] = manual_review_reasons

    if warnings:
        entry["warnings"] = warnings
        entry["needs_manual_review"] = True
        entry["validation_status"] = "warning"
    else:
        entry["needs_manual_review"] = False
        entry["validation_status"] = "ok"

    return entry


def build_ledger_from_portfolio_input_transactions(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a transaction ledger from portfolio_input transactions.

    Returns a ledger dict compatible with build_transaction_ledger.py output.
    """
    normalized: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    valid_count = 0
    invalid_count = 0
    invalid_fund_code_count = 0
    invalid_date_count = 0
    invalid_amount_count = 0
    unknown_transaction_type_count = 0

    for i, raw in enumerate(transactions):
        entry = normalize_portfolio_input_transaction(raw, i)
        entry_warnings = entry.pop("warnings", [])
        if entry_warnings:
            all_warnings.extend(entry_warnings)
            invalid_count += 1
            # Count specific warning types
            for w in entry_warnings:
                if "fund_code" in w:
                    invalid_fund_code_count += 1
                if "trade_date" in w:
                    invalid_date_count += 1
                if "amount" in w:
                    invalid_amount_count += 1
                if "transaction_type" in w:
                    unknown_transaction_type_count += 1
        else:
            valid_count += 1
        normalized.append(entry)

    # Sort by trade_date
    normalized.sort(key=lambda t: t.get("trade_date") or "9999-99-99")

    manual_review_count = sum(1 for t in normalized if t.get("needs_manual_review"))
    manual_review_required_count = sum(1 for t in normalized if t.get("manual_review_required"))

    summary = {
        "total_transactions": len(normalized),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "warning_count": len(all_warnings),
        "manual_review_count": manual_review_count,
        "manual_review_required_count": manual_review_required_count,
        "user_provided_private_input": sum(
            1 for t in normalized if t.get("confirmation_type") == "user_provided_private_input"
        ),
        "with_fund_code": sum(1 for t in normalized if t.get("fund_code")),
        "name_only": sum(1 for t in normalized if not t.get("fund_code") and t.get("fund_name")),
        "with_units": sum(1 for t in normalized if t.get("units") is not None),
        "with_nav": sum(1 for t in normalized if t.get("nav") is not None),
        "ambiguous_portfolio_effect": sum(
            1 for t in normalized if t.get("ambiguous_portfolio_effect")
        ),
        "fee_transaction_count": sum(1 for t in normalized if t.get("fee_transaction")),
        "dividend_transaction_count": sum(1 for t in normalized if t.get("dividend_transaction")),
        "conversion_count": sum(1 for t in normalized if t.get("action") == "conversion"),
        "refund_count": sum(1 for t in normalized if t.get("action") == "refund"),
        "unknown_count": sum(1 for t in normalized if t.get("action") == "unknown"),
        "invalid_fund_code_count": invalid_fund_code_count,
        "invalid_date_count": invalid_date_count,
        "invalid_amount_count": invalid_amount_count,
        "unknown_transaction_type_count": unknown_transaction_type_count,
    }

    return {
        "schema_version": "transaction_ledger.v1",
        "source": "portfolio_input_transactions",
        "transactions": normalized,
        "summary": summary,
        "warnings": all_warnings,
    }


def validate_portfolio_input_transactions(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate portfolio_input transactions without building a ledger.

    Returns counts and warning/error lists. No sensitive content.
    """
    total = len(transactions)
    valid = 0
    invalid_fund_code = 0
    invalid_date = 0
    invalid_amount = 0
    missing_type = 0
    name_only = 0
    with_fund_code = 0

    for i, raw in enumerate(transactions):
        has_error = False

        # Check trade_date
        trade_date = str(raw.get("trade_date", ""))
        if not DATE_RE.match(trade_date):
            invalid_date += 1
            has_error = True

        # Check transaction_type
        raw_type = str(raw.get("transaction_type", "")).lower()
        if raw_type not in TRANSACTION_TYPE_MAP:
            missing_type += 1
            has_error = True

        # Check amount
        amount = raw.get("amount")
        if not isinstance(amount, (int, float)):
            invalid_amount += 1
            has_error = True

        # Check fund_code
        fc = raw.get("fund_code")
        if fc is not None:
            fc_str = str(fc)
            if fc_str and not is_valid_fund_code(fc_str):
                invalid_fund_code += 1
                has_error = True
            elif fc_str:
                with_fund_code += 1

        if not fc and raw.get("fund_name"):
            name_only += 1

        if not has_error:
            valid += 1

    return {
        "total": total,
        "valid": valid,
        "invalid_fund_code": invalid_fund_code,
        "invalid_date": invalid_date,
        "invalid_amount": invalid_amount,
        "missing_type": missing_type,
        "name_only": name_only,
        "with_fund_code": with_fund_code,
    }
