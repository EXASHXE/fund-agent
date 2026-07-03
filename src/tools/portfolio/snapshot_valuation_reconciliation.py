"""Snapshot valuation reconciliation — M7.22.

Reconciles the user's private holdings snapshot with provider NAV data
to produce a valuation baseline for current holdings.

Key rules:
- implied_shares = current_amount_snapshot / unit_nav_snapshot.
- Provider NAV same date → strict NAV reconciliation.
- Provider NAV different date → nav_date_mismatch warning, not error.
- Missing provider NAV → marks partial, does NOT block snapshot baseline.
- amount_diff_pct > threshold → amount_mismatch_manual_review.
- Public summary has no fund codes, amounts, NAV, or shares.
- Private CSV contains full detail but must not be committed.
- No formal investment decision output.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.tools.portfolio.holding_snapshot_reconciliation import (
    HoldingSnapshotReconciliationResult,
)
from src.tools.portfolio.holdings_snapshot import HoldingsSnapshotEntry


# ── Valuation status enumeration ─────────────────────────────────────────

VAL_STATUS_MATCHED_SNAPSHOT_POSITION = "matched_snapshot_position"
VAL_STATUS_SNAPSHOT_ONLY_POSITION = "snapshot_only_position"
VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT = "excluded_probable_not_in_snapshot"
VAL_STATUS_BLOCKED_IDENTITY_MISMATCH = "blocked_identity_mismatch"
VAL_STATUS_BLOCKED_MISSING_NAV = "blocked_missing_nav"

VALID_VAL_STATUSES = frozenset({
    VAL_STATUS_MATCHED_SNAPSHOT_POSITION,
    VAL_STATUS_SNAPSHOT_ONLY_POSITION,
    VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT,
    VAL_STATUS_BLOCKED_IDENTITY_MISMATCH,
    VAL_STATUS_BLOCKED_MISSING_NAV,
})

# ── Reconciliation status enumeration ────────────────────────────────────

VAL_RECON_STATUS_FULLY_RECONCILED = "fully_reconciled"
VAL_RECON_STATUS_NAV_DATE_MISMATCH = "nav_date_mismatch"
VAL_RECON_STATUS_MISSING_NAV_PARTIAL = "missing_nav_partial"
VAL_RECON_STATUS_AMOUNT_MISMATCH_MANUAL_REVIEW = "amount_mismatch_manual_review"
VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED = "manual_review_required"

VALID_VAL_RECON_STATUSES = frozenset({
    VAL_RECON_STATUS_FULLY_RECONCILED,
    VAL_RECON_STATUS_NAV_DATE_MISMATCH,
    VAL_RECON_STATUS_MISSING_NAV_PARTIAL,
    VAL_RECON_STATUS_AMOUNT_MISMATCH_MANUAL_REVIEW,
    VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED,
})

# Default threshold for amount mismatch
DEFAULT_AMOUNT_DIFF_THRESHOLD_PCT = 0.005  # 0.5%


@dataclass
class SnapshotValuationPosition:
    """Per-fund snapshot valuation result (private — contains fund_code, amounts, NAV)."""

    fund_code: str = ""
    valuation_status: str = ""
    unit_nav_snapshot: float | None = None
    current_amount_snapshot: float | None = None
    implied_shares: float | None = None
    nav_date_snapshot: str | None = None
    provider_unit_nav: float | None = None
    provider_nav_date: str | None = None
    nav_diff_pct: float | None = None
    amount_recomputed_from_provider_nav: float | None = None
    amount_diff_abs: float | None = None
    amount_diff_pct: float | None = None
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "valuation_status": self.valuation_status,
            "unit_nav_snapshot": self.unit_nav_snapshot,
            "current_amount_snapshot": self.current_amount_snapshot,
            "implied_shares": self.implied_shares,
            "nav_date_snapshot": self.nav_date_snapshot,
            "provider_unit_nav": self.provider_unit_nav,
            "provider_nav_date": self.provider_nav_date,
            "nav_diff_pct": self.nav_diff_pct,
            "amount_recomputed_from_provider_nav": self.amount_recomputed_from_provider_nav,
            "amount_diff_abs": self.amount_diff_abs,
            "amount_diff_pct": self.amount_diff_pct,
            "blocking_reasons": self.blocking_reasons,
        }


@dataclass
class SnapshotValuationSummary:
    """Aggregate summary of snapshot valuation reconciliation."""

    snapshot_position_count: int = 0
    valuation_ready_position_count: int = 0
    valued_position_count: int = 0
    snapshot_only_position_count: int = 0
    excluded_probable_not_in_snapshot_count: int = 0
    missing_nav_count: int = 0
    total_snapshot_amount: float = 0.0
    total_recomputed_amount: float = 0.0
    total_amount_diff_abs: float = 0.0
    total_amount_diff_pct: float | None = None
    nav_date_mismatch_count: int = 0
    amount_mismatch_count: int = 0
    valuation_reconciliation_status: str = VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED
    full_portfolio_metrics_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_position_count": self.snapshot_position_count,
            "valuation_ready_position_count": self.valuation_ready_position_count,
            "valued_position_count": self.valued_position_count,
            "snapshot_only_position_count": self.snapshot_only_position_count,
            "excluded_probable_not_in_snapshot_count": self.excluded_probable_not_in_snapshot_count,
            "missing_nav_count": self.missing_nav_count,
            "total_snapshot_amount": self.total_snapshot_amount,
            "total_recomputed_amount": self.total_recomputed_amount,
            "total_amount_diff_abs": self.total_amount_diff_abs,
            "total_amount_diff_pct": self.total_amount_diff_pct,
            "nav_date_mismatch_count": self.nav_date_mismatch_count,
            "amount_mismatch_count": self.amount_mismatch_count,
            "valuation_reconciliation_status": self.valuation_reconciliation_status,
            "full_portfolio_metrics_allowed": self.full_portfolio_metrics_allowed,
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Public summary — counts and aggregate quality flags only, no amounts/NAV/shares."""
        return {
            "snapshot_position_count": self.snapshot_position_count,
            "valuation_ready_position_count": self.valuation_ready_position_count,
            "valued_position_count": self.valued_position_count,
            "snapshot_only_position_count": self.snapshot_only_position_count,
            "excluded_probable_not_in_snapshot_count": self.excluded_probable_not_in_snapshot_count,
            "missing_nav_count": self.missing_nav_count,
            "nav_date_mismatch_count": self.nav_date_mismatch_count,
            "amount_mismatch_count": self.amount_mismatch_count,
            "valuation_reconciliation_status": self.valuation_reconciliation_status,
            "full_portfolio_metrics_allowed": self.full_portfolio_metrics_allowed,
        }


@dataclass
class SnapshotValuationResult:
    """Complete result of snapshot valuation reconciliation."""

    summary: SnapshotValuationSummary = field(default_factory=SnapshotValuationSummary)
    positions: list[SnapshotValuationPosition] = field(default_factory=list)
    amount_diff_pct_buckets: dict[str, int] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        """Public summary — no fund codes, amounts, NAV, or shares."""
        result = self.summary.to_public_dict()
        result["amount_diff_pct_buckets"] = self.amount_diff_pct_buckets
        return result


def reconcile_snapshot_valuation(
    snapshot_entries: list[HoldingsSnapshotEntry],
    holding_reconciliation: HoldingSnapshotReconciliationResult,
    nav_provider: Any | None = None,
    identity_mismatch_codes: set[str] | None = None,
    amount_diff_threshold_pct: float = DEFAULT_AMOUNT_DIFF_THRESHOLD_PCT,
) -> SnapshotValuationResult:
    """Reconcile snapshot positions with provider NAV for valuation.

    Args:
        snapshot_entries: HoldingsSnapshotEntry list from load_holdings_snapshot.
        holding_reconciliation: HoldingSnapshotReconciliationResult from reconcile_holdings.
        nav_provider: NAVProvider implementation (optional).
        identity_mismatch_codes: Fund codes with identity mismatches.
        amount_diff_threshold_pct: Threshold for amount mismatch flagging (default 0.5%).

    Returns:
        SnapshotValuationResult with valuation positions and summary.
    """
    if identity_mismatch_codes is None:
        identity_mismatch_codes = set()

    # Build lookup sets from holding reconciliation
    matched_codes: set[str] = set()
    snapshot_only_codes: set[str] = set()
    probable_not_in_snapshot_codes: set[str] = set()

    for diff in holding_reconciliation.private_diff_entries:
        if diff.reconciliation_result == "confirmed":
            matched_codes.add(diff.fund_code)
        elif diff.reconciliation_result == "snapshot_only":
            snapshot_only_codes.add(diff.fund_code)
        elif diff.reconciliation_result == "probable_extra":
            probable_not_in_snapshot_codes.add(diff.fund_code)

    # Build snapshot lookup
    snapshot_by_code: dict[str, HoldingsSnapshotEntry] = {}
    for entry in snapshot_entries:
        if entry.fund_code:
            snapshot_by_code[entry.fund_code] = entry

    positions: list[SnapshotValuationPosition] = []
    valued_count = 0
    snapshot_only_count = 0
    excluded_count = 0
    missing_nav_count = 0
    nav_date_mismatch_count = 0
    amount_mismatch_count = 0
    total_snapshot_amount = 0.0
    total_recomputed_amount = 0.0
    total_amount_diff_abs = 0.0

    # Amount diff buckets
    buckets = {"<=0.1%": 0, "0.1%-0.5%": 0, ">0.5%": 0}

    # Process snapshot entries
    for entry in snapshot_entries:
        code = entry.fund_code
        pos = SnapshotValuationPosition(fund_code=code)

        # Determine valuation status
        if code in identity_mismatch_codes:
            pos.valuation_status = VAL_STATUS_BLOCKED_IDENTITY_MISMATCH
            pos.blocking_reasons.append("identity_mismatch_blocks_valuation")
            positions.append(pos)
            continue

        if code in matched_codes:
            pos.valuation_status = VAL_STATUS_MATCHED_SNAPSHOT_POSITION
        elif code in snapshot_only_codes:
            pos.valuation_status = VAL_STATUS_SNAPSHOT_ONLY_POSITION
            snapshot_only_count += 1
        else:
            # In snapshot but not in reconciliation diff — treat as snapshot_only
            pos.valuation_status = VAL_STATUS_SNAPSHOT_ONLY_POSITION
            snapshot_only_count += 1

        # Snapshot baseline
        pos.unit_nav_snapshot = entry.unit_nav
        pos.current_amount_snapshot = entry.current_amount
        pos.nav_date_snapshot = entry.nav_date

        # Compute implied shares
        if entry.unit_nav and entry.unit_nav > 0 and entry.current_amount is not None:
            pos.implied_shares = entry.current_amount / entry.unit_nav

        # Provider NAV reconciliation
        if nav_provider is not None and code:
            provider_nav_data = None
            if entry.nav_date:
                provider_nav_data = nav_provider.get_trade_date_nav(code, entry.nav_date)
            if provider_nav_data is None:
                provider_nav_data = nav_provider.get_latest_nav(code)

            if provider_nav_data is not None:
                pos.provider_unit_nav = provider_nav_data.get("nav")
                pos.provider_nav_date = provider_nav_data.get("nav_date")

                if pos.provider_unit_nav is not None:
                    # NAV diff
                    if entry.unit_nav and entry.unit_nav > 0:
                        pos.nav_diff_pct = abs(pos.provider_unit_nav - entry.unit_nav) / entry.unit_nav

                    # Date mismatch check
                    if entry.nav_date and pos.provider_nav_date and entry.nav_date != pos.provider_nav_date:
                        nav_date_mismatch_count += 1
                        pos.blocking_reasons.append("nav_date_mismatch")

                    # Recompute amount from provider NAV
                    if pos.implied_shares is not None and pos.provider_unit_nav is not None:
                        pos.amount_recomputed_from_provider_nav = pos.implied_shares * pos.provider_unit_nav

                        if pos.current_amount_snapshot is not None:
                            pos.amount_diff_abs = abs(pos.amount_recomputed_from_provider_nav - pos.current_amount_snapshot)
                            if pos.current_amount_snapshot > 0:
                                pos.amount_diff_pct = pos.amount_diff_abs / pos.current_amount_snapshot

                                # Bucket
                                if pos.amount_diff_pct <= 0.001:
                                    buckets["<=0.1%"] += 1
                                elif pos.amount_diff_pct <= 0.005:
                                    buckets["0.1%-0.5%"] += 1
                                else:
                                    buckets[">0.5%"] += 1

                                # Amount mismatch threshold
                                if pos.amount_diff_pct > amount_diff_threshold_pct:
                                    amount_mismatch_count += 1
                                    pos.blocking_reasons.append("amount_mismatch_exceeds_threshold")

                        total_recomputed_amount += pos.amount_recomputed_from_provider_nav or 0.0
                    else:
                        total_recomputed_amount += entry.current_amount or 0.0
                else:
                    missing_nav_count += 1
                    pos.blocking_reasons.append("provider_nav_unavailable")
                    total_recomputed_amount += entry.current_amount or 0.0
            else:
                missing_nav_count += 1
                pos.blocking_reasons.append("provider_nav_unavailable")
                total_recomputed_amount += entry.current_amount or 0.0

        # Accumulate snapshot amount
        if entry.current_amount is not None:
            total_snapshot_amount += entry.current_amount

        valued_count += 1
        positions.append(pos)

    # Add excluded probable_not_in_snapshot entries (no valuation)
    for code in sorted(probable_not_in_snapshot_codes):
        pos = SnapshotValuationPosition(
            fund_code=code,
            valuation_status=VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT,
            blocking_reasons=["probable_not_in_snapshot_excluded_from_valuation"],
        )
        positions.append(pos)
        excluded_count += 1

    # Compute total amount diff
    total_amount_diff_abs = abs(total_recomputed_amount - total_snapshot_amount)
    total_amount_diff_pct = (
        total_amount_diff_abs / total_snapshot_amount
        if total_snapshot_amount > 0
        else None
    )

    # Determine reconciliation status
    recon_status = _determine_valuation_recon_status(
        missing_nav_count=missing_nav_count,
        nav_date_mismatch_count=nav_date_mismatch_count,
        amount_mismatch_count=amount_mismatch_count,
        identity_mismatch_count=len(identity_mismatch_codes & set(snapshot_by_code.keys())),
    )

    # Full portfolio metrics allowed?
    full_portfolio_metrics_allowed = (
        valued_count == holding_reconciliation.valuation_ready_position_count
        and missing_nav_count == 0
        and amount_mismatch_count == 0
        and len(identity_mismatch_codes & set(snapshot_by_code.keys())) == 0
    )

    summary = SnapshotValuationSummary(
        snapshot_position_count=len(snapshot_entries),
        valuation_ready_position_count=holding_reconciliation.valuation_ready_position_count,
        valued_position_count=valued_count,
        snapshot_only_position_count=snapshot_only_count,
        excluded_probable_not_in_snapshot_count=excluded_count,
        missing_nav_count=missing_nav_count,
        total_snapshot_amount=total_snapshot_amount,
        total_recomputed_amount=total_recomputed_amount,
        total_amount_diff_abs=total_amount_diff_abs,
        total_amount_diff_pct=total_amount_diff_pct,
        nav_date_mismatch_count=nav_date_mismatch_count,
        amount_mismatch_count=amount_mismatch_count,
        valuation_reconciliation_status=recon_status,
        full_portfolio_metrics_allowed=full_portfolio_metrics_allowed,
    )

    return SnapshotValuationResult(
        summary=summary,
        positions=positions,
        amount_diff_pct_buckets=buckets,
    )


def _determine_valuation_recon_status(
    *,
    missing_nav_count: int,
    nav_date_mismatch_count: int,
    amount_mismatch_count: int,
    identity_mismatch_count: int,
) -> str:
    """Determine valuation reconciliation status from counts."""
    if identity_mismatch_count > 0:
        return VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED
    if amount_mismatch_count > 0:
        return VAL_RECON_STATUS_AMOUNT_MISMATCH_MANUAL_REVIEW
    if missing_nav_count > 0:
        return VAL_RECON_STATUS_MISSING_NAV_PARTIAL
    if nav_date_mismatch_count > 0:
        return VAL_RECON_STATUS_NAV_DATE_MISMATCH
    return VAL_RECON_STATUS_FULLY_RECONCILED


def write_snapshot_valuation_diff_csv(
    positions: list[SnapshotValuationPosition],
    output_path: Path,
) -> None:
    """Write private snapshot valuation diff to CSV.

    This file is PRIVATE — must not be committed or appear in public reports.
    """
    fieldnames = [
        "fund_code", "valuation_status",
        "unit_nav_snapshot", "current_amount_snapshot", "implied_shares",
        "nav_date_snapshot", "provider_unit_nav", "provider_nav_date",
        "nav_diff_pct", "amount_recomputed_from_provider_nav",
        "amount_diff_abs", "amount_diff_pct",
        "blocking_reasons", "recommended_action",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pos in positions:
            # Determine recommended action
            action = _recommended_action(pos)
            writer.writerow({
                "fund_code": pos.fund_code,
                "valuation_status": pos.valuation_status,
                "unit_nav_snapshot": pos.unit_nav_snapshot if pos.unit_nav_snapshot is not None else "",
                "current_amount_snapshot": pos.current_amount_snapshot if pos.current_amount_snapshot is not None else "",
                "implied_shares": f"{pos.implied_shares:.6f}" if pos.implied_shares is not None else "",
                "nav_date_snapshot": pos.nav_date_snapshot or "",
                "provider_unit_nav": pos.provider_unit_nav if pos.provider_unit_nav is not None else "",
                "provider_nav_date": pos.provider_nav_date or "",
                "nav_diff_pct": f"{pos.nav_diff_pct:.6f}" if pos.nav_diff_pct is not None else "",
                "amount_recomputed_from_provider_nav": f"{pos.amount_recomputed_from_provider_nav:.2f}" if pos.amount_recomputed_from_provider_nav is not None else "",
                "amount_diff_abs": f"{pos.amount_diff_abs:.2f}" if pos.amount_diff_abs is not None else "",
                "amount_diff_pct": f"{pos.amount_diff_pct:.6f}" if pos.amount_diff_pct is not None else "",
                "blocking_reasons": "; ".join(pos.blocking_reasons),
                "recommended_action": action,
            })


def _recommended_action(pos: SnapshotValuationPosition) -> str:
    """Determine recommended action for a position."""
    if pos.valuation_status == VAL_STATUS_BLOCKED_IDENTITY_MISMATCH:
        return "resolve_identity_before_valuation"
    if pos.valuation_status == VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT:
        return "user_confirmation_needed"
    if "amount_mismatch_exceeds_threshold" in pos.blocking_reasons:
        return "manual_review_amount_mismatch"
    if "nav_date_mismatch" in pos.blocking_reasons:
        return "verify_nav_date_consistency"
    if "provider_nav_unavailable" in pos.blocking_reasons:
        return "use_snapshot_nav_as_baseline"
    if pos.valuation_status == VAL_STATUS_SNAPSHOT_ONLY_POSITION:
        return "include_in_snapshot_valuation_only"
    return "include_in_valuation"
