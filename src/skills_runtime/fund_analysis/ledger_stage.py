"""Ledger-derived portfolio and reconciliation helpers for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput
from src.tools.portfolio.ledger_snapshot import (
    build_position_snapshot_from_transactions,
    reconcile_snapshot_with_portfolio,
)

from .context import FundAnalysisContext, StageResult
from .input_stage import dict_or_empty, has_related_entities
from .status_stage import failed_output


def resolve_portfolio_context(
    skill_input: SkillInput,
    payload: dict[str, Any],
) -> StageResult:
    portfolio = dict_or_empty(payload.get("portfolio"))
    positions = portfolio.get("positions")

    source_of_truth: str | None = None
    derived_snapshot: dict[str, Any] | None = None
    reconciliation_report: dict[str, Any] | None = None

    has_host_positions = isinstance(positions, list) and len(positions) > 0
    has_transactions = isinstance(payload.get("transactions"), list) and len(payload["transactions"]) > 0
    has_current_nav = isinstance(payload.get("current_nav"), dict) and len(payload["current_nav"]) > 0

    if has_host_positions:
        source_of_truth = "host_portfolio"
    elif has_transactions and has_current_nav:
        # Derive portfolio snapshot from transactions + current_nav
        as_of_date = portfolio.get("as_of_date", payload.get("as_of_date", ""))
        if not as_of_date:
            return StageResult(
                output=failed_output(
                    skill_input,
                    "INVALID_INPUT",
                    "Cannot derive portfolio from transactions: missing as_of_date",
                )
            )
        try:
            derived_snapshot = build_position_snapshot_from_transactions(
                transactions=payload["transactions"],
                current_nav_by_fund=payload["current_nav"],
                as_of_date=as_of_date,
                options=payload.get("settlement_options"),
            )
            source_of_truth = "derived_from_transactions"
        except Exception as exc:
            return StageResult(
                output=failed_output(
                    skill_input,
                    "INTERNAL_ERROR",
                    f"Failed to derive portfolio from transactions: {exc}",
                    details={"error_type": type(exc).__name__},
                )
            )
    elif not has_host_positions:
        if has_related_entities(payload, skill_input):
            return StageResult(context=FundAnalysisContext(payload, baseline_only=True))
        return StageResult(
            output=failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill requires portfolio.positions or transactions+current_nav or related_entities",
            )
        )

    # If both host portfolio and derivable transactions exist, reconcile
    if has_host_positions and has_transactions and has_current_nav:
        try:
            derived_for_reconcile = build_position_snapshot_from_transactions(
                transactions=payload["transactions"],
                current_nav_by_fund=payload["current_nav"],
                as_of_date=portfolio.get("as_of_date", payload.get("as_of_date", "")),
                options=payload.get("settlement_options"),
            )
            reconciliation_report = reconcile_snapshot_with_portfolio(
                derived_for_reconcile, portfolio
            )
        except Exception:
            # Reconciliation failure should not block analysis
            pass

    return StageResult(
        context=FundAnalysisContext(
            payload=payload,
            source_of_truth=source_of_truth,
            derived_snapshot=derived_snapshot,
            reconciliation_report=reconciliation_report,
        )
    )


def portfolio_from_derived_snapshot(
    payload: dict[str, Any],
    derived_snapshot: dict[str, Any],
) -> dict[str, Any]:
    positions = derived_snapshot.get("positions", [])
    # Build portfolio dict from snapshot positions
    total_value = 0.0
    for pos in positions:
        cv = pos.get("current_value") or 0.0
        total_value += cv
    return {
        "as_of_date": derived_snapshot.get("as_of_date", payload.get("as_of_date", "")),
        "total_value": total_value,
        "cash_available": payload.get("current_nav", {}).get("_cash_available",
                            derived_snapshot.get("cashflow_summary", {}).get("implied_cash", 0.0)),
        "positions": [
            {
                "fund_code": pos.get("fund_code", ""),
                "fund_name": pos.get("fund_code", ""),  # name unknown from ledger only
                "shares": pos.get("shares"),
                "current_value": pos.get("current_value"),
                "total_cost": pos.get("total_cost"),
                "tags": [],
            }
            for pos in positions
        ],
    }


def build_ledger_quality_summary(
    derived_snapshot: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    # Build ledger quality summary
    invalid = derived_snapshot.get("invalid_events_count", 0)
    unresolved_events = derived_snapshot.get("unresolved_events", [])
    unresolved_count = len(unresolved_events)
    ledger_quality = {
        "invalid_events_count": invalid,
        "unresolved_events_count": unresolved_count,
        "is_complete": invalid == 0 and unresolved_count == 0,
        "limitations": [],
    }
    if invalid > 0:
        ledger_quality["limitations"].append(
            f"{invalid} transaction event(s) were invalid and excluded"
        )
        warnings.append(
            f"ledger contains {invalid} invalid transaction event(s); "
            f"derived portfolio may be incomplete"
        )
    if unresolved_count > 0:
        ledger_quality["limitations"].append(
            f"{unresolved_count} transaction event(s) could not be "
            f"resolved (e.g. amount-only BUY/SELL with no shares/nav)"
        )
        warnings.append(
            f"ledger contains {unresolved_count} unresolved transaction "
            f"event(s); shares and cost basis may be incomplete"
        )
    return ledger_quality
