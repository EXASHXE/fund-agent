"""Holdings snapshot reconciliation — M7.21.

Reconciles the user's private holdings snapshot with transaction-derived
current holding discovery. Determines which funds are valuation-ready,
flags mismatches, and produces a reconciliation result.

Key rules:
- Snapshot is NOT an identity oracle — cannot set provider_verified.
- fund_code in both snapshot and probable_current → confirmed_current.
- Snapshot-only position → allowed for snapshot valuation only.
- Probable not in snapshot → excluded from snapshot valuation set.
- Closed but in snapshot → manual_review_required.
- Identity mismatch → block full valuation.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    CurrentHoldingCandidate,
    is_current_holding,
)
from src.tools.portfolio.holdings_snapshot import HoldingsSnapshotEntry


# ── Reconciliation status enumeration ────────────────────────────────────

RECON_STATUS_FULLY_RECONCILED = "fully_reconciled"
RECON_STATUS_SNAPSHOT_CONFIRMS_SUBSET = "snapshot_confirms_subset"
RECON_STATUS_TRANSACTION_PROBABLE_EXTRA = "transaction_probable_extra"
RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS = "snapshot_has_unseen_positions"
RECON_STATUS_IDENTITY_MISMATCH = "identity_mismatch"
RECON_STATUS_MANUAL_REVIEW_REQUIRED = "manual_review_required"

VALID_RECON_STATUSES = frozenset({
    RECON_STATUS_FULLY_RECONCILED,
    RECON_STATUS_SNAPSHOT_CONFIRMS_SUBSET,
    RECON_STATUS_TRANSACTION_PROBABLE_EXTRA,
    RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS,
    RECON_STATUS_IDENTITY_MISMATCH,
    RECON_STATUS_MANUAL_REVIEW_REQUIRED,
})


@dataclass
class ReconciliationDiffEntry:
    """Per-fund reconciliation result (private — contains fund_code)."""

    fund_code: str = ""
    snapshot_status: str = ""  # present, absent
    transaction_discovery_status: str = ""  # probable, closed, history_only, absent
    reconciliation_result: str = ""  # confirmed, snapshot_only, probable_extra, closed_mismatch, identity_mismatch
    current_amount: float | None = None
    unit_nav: float | None = None
    nav_date: str | None = None
    blocking_reason: str = ""
    recommended_action: str = ""


@dataclass
class HoldingSnapshotReconciliationResult:
    """Result of reconciling snapshot with transaction-derived holdings."""

    snapshot_position_count: int = 0
    probable_current_count: int = 0
    confirmed_current_count: int = 0
    matched_snapshot_count: int = 0
    probable_not_in_snapshot_count: int = 0
    snapshot_not_in_probable_count: int = 0
    closed_but_in_snapshot_count: int = 0
    identity_mismatch_count: int = 0
    valuation_ready_position_count: int = 0
    reconciliation_status: str = RECON_STATUS_MANUAL_REVIEW_REQUIRED
    blocking_reasons: list[str] = field(default_factory=list)
    private_diff_entries: list[ReconciliationDiffEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_position_count": self.snapshot_position_count,
            "probable_current_count": self.probable_current_count,
            "confirmed_current_count": self.confirmed_current_count,
            "matched_snapshot_count": self.matched_snapshot_count,
            "probable_not_in_snapshot_count": self.probable_not_in_snapshot_count,
            "snapshot_not_in_probable_count": self.snapshot_not_in_probable_count,
            "closed_but_in_snapshot_count": self.closed_but_in_snapshot_count,
            "identity_mismatch_count": self.identity_mismatch_count,
            "valuation_ready_position_count": self.valuation_ready_position_count,
            "reconciliation_status": self.reconciliation_status,
            "blocking_reasons": self.blocking_reasons,
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Public summary — counts only, no fund codes or amounts."""
        return self.to_dict()


def reconcile_holdings(
    candidates: list[CurrentHoldingCandidate],
    snapshot_entries: list[HoldingsSnapshotEntry],
    identity_resolution: dict[str, Any] | None = None,
) -> HoldingSnapshotReconciliationResult:
    """Reconcile transaction-derived holdings with snapshot.

    Args:
        candidates: CurrentHoldingCandidate list from discover_current_holdings.
        snapshot_entries: HoldingsSnapshotEntry list from load_holdings_snapshot.
        identity_resolution: Fund identity resolution dict.

    Returns:
        HoldingSnapshotReconciliationResult with reconciliation status.
    """
    result = HoldingSnapshotReconciliationResult()

    # Build lookup maps
    snapshot_by_code: dict[str, HoldingsSnapshotEntry] = {}
    for entry in snapshot_entries:
        if entry.fund_code:
            snapshot_by_code[entry.fund_code] = entry

    # Build identity lookup for mismatch detection
    identity_lookup: dict[str, str] = {}
    if identity_resolution:
        fund_list = identity_resolution.get("funds", identity_resolution.get("resolutions", []))
        for fund in fund_list:
            fc = fund.get("resolved_fund_code") or fund.get("fund_code", "")
            ivs = fund.get("identity_verification_status", "")
            if fc:
                identity_lookup[fc] = ivs

    # Build candidate maps
    probable_by_code: dict[str, CurrentHoldingCandidate] = {}
    closed_by_code: dict[str, CurrentHoldingCandidate] = {}
    all_candidate_codes: set[str] = set()

    for cand in candidates:
        all_candidate_codes.add(cand.fund_code)
        if cand.lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE:
            probable_by_code[cand.fund_code] = cand
        elif cand.lifecycle_status == HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE:
            closed_by_code[cand.fund_code] = cand

    snapshot_codes = set(snapshot_by_code.keys())
    probable_codes = set(probable_by_code.keys())
    closed_codes = set(closed_by_code.keys())

    # Compute counts
    result.snapshot_position_count = len(snapshot_entries)
    result.probable_current_count = len(probable_by_code)

    # Matched: fund_code in both snapshot and probable_current → confirmed
    matched_codes = snapshot_codes & probable_codes
    result.matched_snapshot_count = len(matched_codes)
    result.confirmed_current_count = len(matched_codes)

    # Probable not in snapshot
    probable_not_in_snapshot = probable_codes - snapshot_codes
    result.probable_not_in_snapshot_count = len(probable_not_in_snapshot)

    # Snapshot not in probable
    snapshot_not_in_probable = snapshot_codes - probable_codes - closed_codes
    result.snapshot_not_in_probable_count = len(snapshot_not_in_probable)

    # Closed but in snapshot
    closed_but_in_snapshot = closed_codes & snapshot_codes
    result.closed_but_in_snapshot_count = len(closed_but_in_snapshot)

    # Identity mismatch check
    identity_mismatch_count = 0
    for code in snapshot_codes:
        ivs = identity_lookup.get(code, "")
        if ivs in ("name_only", "invalid_code", "code_name_mismatch"):
            identity_mismatch_count += 1
    result.identity_mismatch_count = identity_mismatch_count

    # Valuation-ready: confirmed (matched) + snapshot-only positions
    # Probable-not-in-snapshot are excluded from snapshot valuation set
    result.valuation_ready_position_count = (
        result.confirmed_current_count + result.snapshot_not_in_probable_count
    )

    # Build private diff entries
    diff_entries: list[ReconciliationDiffEntry] = []

    # Matched entries → confirmed
    for code in sorted(matched_codes):
        snap = snapshot_by_code[code]
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code,
            snapshot_status="present",
            transaction_discovery_status="probable",
            reconciliation_result="confirmed",
            current_amount=snap.current_amount,
            unit_nav=snap.unit_nav,
            nav_date=snap.nav_date,
            blocking_reason="",
            recommended_action="include_in_valuation",
        ))

    # Probable not in snapshot
    for code in sorted(probable_not_in_snapshot):
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code,
            snapshot_status="absent",
            transaction_discovery_status="probable",
            reconciliation_result="probable_extra",
            blocking_reason="not_in_snapshot_cannot_confirm",
            recommended_action="user_confirmation_needed",
        ))

    # Snapshot not in probable (and not closed)
    for code in sorted(snapshot_not_in_probable):
        snap = snapshot_by_code[code]
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code,
            snapshot_status="present",
            transaction_discovery_status="absent",
            reconciliation_result="snapshot_only",
            current_amount=snap.current_amount,
            unit_nav=snap.unit_nav,
            nav_date=snap.nav_date,
            blocking_reason="",
            recommended_action="include_in_snapshot_valuation_only",
        ))

    # Closed but in snapshot
    for code in sorted(closed_but_in_snapshot):
        snap = snapshot_by_code[code]
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code,
            snapshot_status="present",
            transaction_discovery_status="closed",
            reconciliation_result="closed_mismatch",
            current_amount=snap.current_amount,
            unit_nav=snap.unit_nav,
            nav_date=snap.nav_date,
            blocking_reason="closed_but_in_snapshot_manual_review",
            recommended_action="manual_review_position_status",
        ))

    result.private_diff_entries = diff_entries

    # Determine reconciliation status
    blocking_reasons: list[str] = []

    if identity_mismatch_count > 0:
        result.reconciliation_status = RECON_STATUS_IDENTITY_MISMATCH
        blocking_reasons.append("identity_mismatch_in_snapshot")
    elif closed_but_in_snapshot:
        result.reconciliation_status = RECON_STATUS_MANUAL_REVIEW_REQUIRED
        blocking_reasons.append("closed_position_in_snapshot")
    elif probable_not_in_snapshot and snapshot_not_in_probable:
        result.reconciliation_status = RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS
        blocking_reasons.append("snapshot_has_positions_not_in_transactions")
        blocking_reasons.append("transaction_has_positions_not_in_snapshot")
    elif probable_not_in_snapshot:
        result.reconciliation_status = RECON_STATUS_TRANSACTION_PROBABLE_EXTRA
        blocking_reasons.append("transaction_probable_not_in_snapshot")
    elif snapshot_not_in_probable:
        result.reconciliation_status = RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS
        blocking_reasons.append("snapshot_has_positions_not_in_transactions")
    elif matched_codes and not probable_not_in_snapshot and not snapshot_not_in_probable:
        # All snapshot positions matched, no extras
        result.reconciliation_status = RECON_STATUS_FULLY_RECONCILED
    else:
        result.reconciliation_status = RECON_STATUS_SNAPSHOT_CONFIRMS_SUBSET

    result.blocking_reasons = blocking_reasons

    return result


def write_reconciliation_diff_csv(
    diff_entries: list[ReconciliationDiffEntry],
    output_path: Path,
) -> None:
    """Write private reconciliation diff to CSV.

    This file is PRIVATE — must not be committed or appear in public reports.
    """
    fieldnames = [
        "fund_code", "snapshot_status", "transaction_discovery_status",
        "reconciliation_result", "current_amount", "unit_nav", "nav_date",
        "blocking_reason", "recommended_action",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in diff_entries:
            writer.writerow({
                "fund_code": entry.fund_code,
                "snapshot_status": entry.snapshot_status,
                "transaction_discovery_status": entry.transaction_discovery_status,
                "reconciliation_result": entry.reconciliation_result,
                "current_amount": entry.current_amount if entry.current_amount is not None else "",
                "unit_nav": entry.unit_nav if entry.unit_nav is not None else "",
                "nav_date": entry.nav_date or "",
                "blocking_reason": entry.blocking_reason,
                "recommended_action": entry.recommended_action,
            })
