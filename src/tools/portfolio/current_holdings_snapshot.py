"""Current holdings snapshot importer — authoritative portfolio state (M7.5).

Loads, validates, and normalizes user-provided holdings snapshot data.
A holdings snapshot represents the current state of the portfolio (shares,
NAV, current value) as opposed to transaction history which records past events.

Key rules:
- Empty values stay empty (None) — never convert missing data to zero
- current_value from snapshot is platform_reported, not reconstructed
- holding_profit is platform_reported_profit, must not be confused with reconstructed P&L
- Snapshot + transaction conflict → flag reconciliation_gap, don't silently merge
- fund_code empty → identity resolution will attempt to match by fund_name
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "current_holdings_snapshot.v1"

# Required CSV columns (fund_name is the minimum for a useful row)
_REQUIRED_CSV_COLUMNS = {"fund_name"}
_ALL_CSV_COLUMNS = [
    "as_of_date", "fund_code", "fund_name", "shares", "latest_nav",
    "nav_date", "current_value", "holding_cost", "holding_profit",
    "holding_profit_pct", "source", "user_verified",
]


def load_current_holdings_snapshot(path: Path) -> dict[str, Any]:
    """Load a current holdings snapshot from CSV or JSON file.

    Args:
        path: Path to the snapshot file (.csv or .json).

    Returns:
        Normalized snapshot dict with schema_version, as_of_date,
        positions, and summary.

    Raises:
        ValueError: If file format is unsupported or data is invalid.
        FileNotFoundError: If path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Holdings snapshot not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw_data = _load_csv(path)
    elif suffix == ".json":
        raw_data = _load_json(path)
    else:
        raise ValueError(f"Unsupported holdings snapshot format: {suffix}. Use .csv or .json")

    return normalize_current_holdings_snapshot(raw_data)


def validate_current_holdings_snapshot(data: dict[str, Any]) -> list[str]:
    """Validate a holdings snapshot dict. Returns list of validation errors.

    Empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        errors.append("Snapshot must be a dict")
        return errors

    positions = data.get("positions", [])
    if not isinstance(positions, list):
        errors.append("positions must be a list")
        return errors

    for i, pos in enumerate(positions):
        if not isinstance(pos, dict):
            errors.append(f"Position {i} must be a dict")
            continue

        # fund_name is required
        if not pos.get("fund_name"):
            errors.append(f"Position {i}: fund_name is required")

        # fund_code must be 6 digits if provided
        fc = pos.get("fund_code")
        if fc is not None and fc != "":
            fc_str = str(fc).strip()
            if not (fc_str.isdigit() and len(fc_str) == 6):
                errors.append(f"Position {i}: fund_code must be 6 digits, got '{fc_str}'")

        # shares must be positive if provided
        shares = pos.get("shares")
        if shares is not None:
            try:
                s = float(shares)
                if s < 0:
                    errors.append(f"Position {i}: shares must be non-negative, got {s}")
            except (TypeError, ValueError):
                errors.append(f"Position {i}: shares must be numeric, got '{shares}'")

        # current_value must be positive if provided
        cv = pos.get("current_value")
        if cv is not None:
            try:
                v = float(cv)
                if v < 0:
                    errors.append(f"Position {i}: current_value must be non-negative, got {v}")
            except (TypeError, ValueError):
                errors.append(f"Position {i}: current_value must be numeric, got '{cv}'")

        # user_verified must be boolean-like if provided
        uv = pos.get("user_verified")
        if uv is not None and str(uv).lower() not in ("true", "false", "1", "0", ""):
            errors.append(f"Position {i}: user_verified must be true/false, got '{uv}'")

    return errors


def normalize_current_holdings_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw snapshot data into canonical form.

    - Converts numeric strings to floats
    - Converts empty strings to None
    - Normalizes user_verified to bool
    - Computes summary statistics
    """
    as_of_date = data.get("as_of_date", "")
    source = data.get("source", "user_provided_holdings_snapshot")
    raw_positions = data.get("positions", [])

    positions: list[dict[str, Any]] = []
    for raw in raw_positions:
        pos = _normalize_position(raw)
        positions.append(pos)

    summary = _compute_summary(positions)

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_date": str(as_of_date) if as_of_date else "",
        "source": source,
        "positions": positions,
        "summary": summary,
    }


def _normalize_position(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single position dict."""
    fund_code = _clean_string(raw.get("fund_code"))
    fund_name = _clean_string(raw.get("fund_name"))

    # If fund_code is empty/missing but fund_name exists, leave code empty
    # Identity resolution will handle it later
    if fund_code is not None and not (fund_code.isdigit() and len(fund_code) == 6):
        # Not a valid 6-digit code — treat as empty
        fund_code = None

    shares = _clean_float(raw.get("shares"))
    latest_nav = _clean_float(raw.get("latest_nav"))
    nav_date = _clean_string(raw.get("nav_date"))
    current_value = _clean_float(raw.get("current_value"))
    holding_cost = _clean_float(raw.get("holding_cost"))
    holding_profit = _clean_float(raw.get("holding_profit"))
    holding_profit_pct = _clean_float(raw.get("holding_profit_pct"))
    pos_source = _clean_string(raw.get("source"))
    user_verified = _clean_bool(raw.get("user_verified"))

    # Determine identity_verification_status
    if fund_code and user_verified:
        identity_verification_status = "user_verified_override"
    elif fund_code:
        identity_verification_status = "unverified_code"
    else:
        identity_verification_status = "name_only"

    # Determine valuation_source
    if shares is not None and latest_nav is not None:
        valuation_source = "authoritative_holdings_snapshot"
    elif current_value is not None:
        valuation_source = "platform_reported_current_value"
    else:
        valuation_source = "holdings_snapshot_no_valuation"

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "shares": shares,
        "latest_nav": latest_nav,
        "nav_date": nav_date,
        "current_value": current_value,
        "holding_cost": holding_cost,
        "holding_profit": holding_profit,
        "holding_profit_pct": holding_profit_pct,
        "source": pos_source,
        "user_verified": user_verified,
        "identity_verification_status": identity_verification_status,
        "valuation_source": valuation_source,
    }


def _compute_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics from normalized positions."""
    positions_total = len(positions)
    shares_available_count = sum(1 for p in positions if p.get("shares") is not None)
    current_value_available_count = sum(1 for p in positions if p.get("current_value") is not None)
    user_verified_count = sum(1 for p in positions if p.get("user_verified") is True)
    fund_code_available_count = sum(1 for p in positions if p.get("fund_code") is not None)
    latest_nav_available_count = sum(1 for p in positions if p.get("latest_nav") is not None)
    platform_reported_profit_count = sum(1 for p in positions if p.get("holding_profit") is not None)

    # How many positions can be valued from the snapshot alone
    valued_from_shares_nav = sum(
        1 for p in positions
        if p.get("shares") is not None and p.get("latest_nav") is not None
    )
    valued_from_current_value = sum(
        1 for p in positions
        if p.get("current_value") is not None
        and p.get("shares") is None  # only current_value, no shares
    )
    valued_count = valued_from_shares_nav + valued_from_current_value

    return {
        "positions_total": positions_total,
        "shares_available_count": shares_available_count,
        "current_value_available_count": current_value_available_count,
        "user_verified_count": user_verified_count,
        "fund_code_available_count": fund_code_available_count,
        "latest_nav_available_count": latest_nav_available_count,
        "platform_reported_profit_count": platform_reported_profit_count,
        "valued_from_shares_nav_count": valued_from_shares_nav,
        "valued_from_current_value_only_count": valued_from_current_value,
        "valued_count": valued_count,
    }


# ── Internal loaders ────────────────────────────────────────────────────


def _load_csv(path: Path) -> dict[str, Any]:
    """Load holdings snapshot from CSV."""
    positions: list[dict[str, Any]] = []
    as_of_date = ""

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract as_of_date from first row if present
            if not as_of_date and row.get("as_of_date"):
                as_of_date = row["as_of_date"]

            pos: dict[str, Any] = {}
            for col in _ALL_CSV_COLUMNS:
                if col == "as_of_date":
                    continue  # global, not per-position
                val = row.get(col)
                if val is not None and val.strip() != "":
                    pos[col] = val.strip()
                # else: omit the key entirely (None equivalent)
            positions.append(pos)

    return {
        "as_of_date": as_of_date,
        "source": "user_provided_holdings_snapshot",
        "positions": positions,
    }


def _load_json(path: Path) -> dict[str, Any]:
    """Load holdings snapshot from JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("JSON holdings snapshot must be a dict/object")

    # If it already has the full structure, return as-is
    if "positions" in data:
        return data

    # Otherwise wrap it
    return {
        "as_of_date": data.get("as_of_date", ""),
        "source": data.get("source", "user_provided_holdings_snapshot"),
        "positions": data.get("positions", []),
    }


# ── Type coercion helpers ───────────────────────────────────────────────


def _clean_string(value: Any) -> str | None:
    """Clean a string value. Returns None for empty/missing."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _clean_float(value: Any) -> float | None:
    """Clean a numeric value. Returns None for empty/missing. Never returns 0 for missing."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _clean_bool(value: Any) -> bool | None:
    """Clean a boolean value. Returns None for empty/missing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    return None
