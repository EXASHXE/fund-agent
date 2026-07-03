"""Private holdings snapshot loader — M7.21.

Loads and validates the user's current holdings snapshot from a private CSV.
The snapshot confirms which funds are currently held, provides a valuation
baseline, and participates in reconciliation with transaction-derived holdings.

Key rules:
- Snapshot is PRIVATE — never committed, never in public report.
- Snapshot is NOT an identity oracle — cannot set provider_verified.
- Snapshot can only: confirm current holding lifecycle, provide valuation
  baseline, participate in reconciliation.
- fund_code must be 6 digits.
- current_amount must be non-negative.
- unit_nav must be > 0.
- nav_date must be YYYY-MM-DD if present.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "private_holdings_snapshot.v2"

# Allowed source values
ALLOWED_SOURCES = frozenset({
    "alipay_holdings_snapshot",
    "manual_snapshot",
    "broker_snapshot",
})

# Allowed confidence values
ALLOWED_CONFIDENCES = frozenset({"high", "medium", "low"})

# CSV columns
CSV_COLUMNS = [
    "fund_name", "fund_code", "nav_date", "unit_nav",
    "current_amount", "source", "confidence", "notes",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class HoldingsSnapshotEntry:
    """A single position from the holdings snapshot."""

    fund_name: str = ""
    fund_code: str = ""
    nav_date: str | None = None
    unit_nav: float | None = None
    current_amount: float | None = None
    source: str = "manual_snapshot"
    confidence: str = "medium"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_name": self.fund_name,
            "fund_code": self.fund_code,
            "nav_date": self.nav_date,
            "unit_nav": self.unit_nav,
            "current_amount": self.current_amount,
            "source": self.source,
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass
class HoldingsSnapshotSummary:
    """Aggregate summary of holdings snapshot."""

    position_count: int = 0
    fund_code_available_count: int = 0
    nav_available_count: int = 0
    current_amount_available_count: int = 0
    high_confidence_count: int = 0
    source_counts: dict[str, int] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_count": self.position_count,
            "fund_code_available_count": self.fund_code_available_count,
            "nav_available_count": self.nav_available_count,
            "current_amount_available_count": self.current_amount_available_count,
            "high_confidence_count": self.high_confidence_count,
            "source_counts": self.source_counts,
            "validation_errors": self.validation_errors,
        }


def validate_holdings_snapshot(entries: list[HoldingsSnapshotEntry]) -> list[str]:
    """Validate snapshot entries. Returns list of validation errors.

    Empty list means valid.
    """
    errors: list[str] = []

    for i, entry in enumerate(entries):
        # fund_code must be 6 digits
        if not entry.fund_code:
            errors.append(f"Row {i+1}: fund_code is required")
        elif not (entry.fund_code.isdigit() and len(entry.fund_code) == 6):
            errors.append(f"Row {i+1}: fund_code must be 6 digits, got '{entry.fund_code}'")

        # current_amount must be non-negative
        if entry.current_amount is not None and entry.current_amount < 0:
            errors.append(f"Row {i+1}: current_amount must be non-negative")

        # unit_nav must be > 0
        if entry.unit_nav is not None and entry.unit_nav <= 0:
            errors.append(f"Row {i+1}: unit_nav must be > 0")

        # nav_date format
        if entry.nav_date and not DATE_RE.match(entry.nav_date):
            errors.append(f"Row {i+1}: nav_date must be YYYY-MM-DD, got '{entry.nav_date}'")

        # source must be valid
        if entry.source and entry.source not in ALLOWED_SOURCES:
            errors.append(f"Row {i+1}: source must be one of {sorted(ALLOWED_SOURCES)}")

        # confidence must be valid
        if entry.confidence and entry.confidence not in ALLOWED_CONFIDENCES:
            errors.append(f"Row {i+1}: confidence must be one of {sorted(ALLOWED_CONFIDENCES)}")

    return errors


def load_holdings_snapshot(path: Path) -> tuple[list[HoldingsSnapshotEntry], HoldingsSnapshotSummary]:
    """Load a private holdings snapshot from CSV.

    Args:
        path: Path to the private CSV file.

    Returns:
        Tuple of (entries, summary).

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If file format is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Holdings snapshot not found: {path}")

    if path.suffix.lower() != ".csv":
        raise ValueError(f"Unsupported snapshot format: {path.suffix}. Use .csv")

    entries: list[HoldingsSnapshotEntry] = []
    source_counts: dict[str, int] = {}

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys
            clean = {(k or "").strip(): (v or "").strip() for k, v in row.items()}

            fund_code = clean.get("fund_code", "")
            fund_name = clean.get("fund_name", "")

            # Parse numeric fields
            unit_nav = _parse_float(clean.get("unit_nav"))
            current_amount = _parse_float(clean.get("current_amount"))

            nav_date = clean.get("nav_date", "") or None
            source = clean.get("source", "manual_snapshot") or "manual_snapshot"
            confidence = clean.get("confidence", "medium") or "medium"
            notes = clean.get("notes", "")

            entry = HoldingsSnapshotEntry(
                fund_name=fund_name,
                fund_code=fund_code,
                nav_date=nav_date,
                unit_nav=unit_nav,
                current_amount=current_amount,
                source=source,
                confidence=confidence,
                notes=notes,
            )
            entries.append(entry)

            # Track source counts
            source_counts[source] = source_counts.get(source, 0) + 1

    # Validate
    validation_errors = validate_holdings_snapshot(entries)

    # Build summary
    summary = HoldingsSnapshotSummary(
        position_count=len(entries),
        fund_code_available_count=sum(1 for e in entries if e.fund_code),
        nav_available_count=sum(1 for e in entries if e.unit_nav is not None),
        current_amount_available_count=sum(1 for e in entries if e.current_amount is not None),
        high_confidence_count=sum(1 for e in entries if e.confidence == "high"),
        source_counts=source_counts,
        validation_errors=validation_errors,
    )

    return entries, summary


def _parse_float(val: str | None) -> float | None:
    """Parse a float value, returning None for empty/missing."""
    if not val or val.strip() in ("", "-"):
        return None
    try:
        return float(val.strip().replace(",", ""))
    except (ValueError, TypeError):
        return None
