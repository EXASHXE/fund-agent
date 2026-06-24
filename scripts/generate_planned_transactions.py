#!/usr/bin/env python3
"""Generate planned transactions from investment plan YAML.

Reads an investment_plan YAML file and generates scheduled/expected_submitted/
pending/rule_confirmed transactions based on the plan parameters and as-of date.

Usage:
    python scripts/generate_planned_transactions.py \
        --plan private_data/investment_plan.private.yaml \
        --nav-snapshot private_data/nav_snapshot.private.json \
        --as-of-date 2025-05-19 \
        --output private_data/planned_transactions.private.json

Respects assume_auto_execution, T+ rules, trading days, QDII lag.
No actual order execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

from src.tools.calendar.dates import is_business_day, next_business_day


def _parse_date(val) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


_DOW_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def _day_of_week_to_int(dow: str | None) -> int | None:
    if not dow:
        return None
    return _DOW_MAP.get(dow.lower())


def _generate_schedule_dates(
    frequency: str,
    start_date: date,
    end_date: date,
    day_of_week: str | None = None,
    day_of_month: int | None = None,
    specific_date: date | None = None,
    skip_non_trading: bool = True,
    next_trading_on_skip: bool = True,
) -> list[date]:
    """Generate all scheduled dates for a plan between start_date and end_date."""
    dates = []

    if frequency == "one_off":
        if specific_date and start_date <= specific_date <= end_date:
            if skip_non_trading and not is_business_day(specific_date):
                if next_trading_on_skip:
                    dates.append(next_business_day(specific_date - timedelta(days=1)))
            else:
                dates.append(specific_date)
        return dates

    if frequency == "daily":
        seen = set()
        cursor = start_date
        while cursor <= end_date:
            target = cursor
            if is_business_day(cursor) or not skip_non_trading:
                target = cursor
            elif next_trading_on_skip:
                target = next_business_day(cursor - timedelta(days=1))
            else:
                cursor += timedelta(days=1)
                continue
            if target not in seen and target <= end_date:
                dates.append(target)
                seen.add(target)
            cursor += timedelta(days=1)
        return dates

    if frequency in ("weekly", "biweekly"):
        target_dow = _day_of_week_to_int(day_of_week)
        step = 7 if frequency == "weekly" else 14
        seen = set()
        cursor = start_date
        while cursor <= end_date:
            if target_dow is not None:
                days_ahead = target_dow - cursor.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                next_occ = cursor + timedelta(days=days_ahead)
            else:
                next_occ = cursor

            if next_occ > end_date:
                break
            if next_occ < start_date:
                cursor = next_occ + timedelta(days=step)
                continue

            if is_business_day(next_occ):
                target = next_occ
            elif next_trading_on_skip:
                target = next_business_day(next_occ - timedelta(days=1))
            else:
                cursor = next_occ + timedelta(days=step)
                continue

            if target <= end_date and target not in seen:
                dates.append(target)
                seen.add(target)

            cursor = next_occ + timedelta(days=step)
        return dates

    if frequency == "monthly":
        cursor = start_date
        day = day_of_month or start_date.day
        while True:
            try:
                target = cursor.replace(day=day)
            except ValueError:
                # Day exceeds month length -> use last day
                if cursor.month == 12:
                    next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
                else:
                    next_month = cursor.replace(month=cursor.month + 1, day=1)
                target = next_month - timedelta(days=1)

            if target > end_date:
                break
            if target < start_date:
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1)
                continue

            if is_business_day(target):
                dates.append(target)
            elif next_trading_on_skip:
                adj = next_business_day(target - timedelta(days=1))
                if adj <= end_date:
                    dates.append(adj)

            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
        return dates

    return dates


def _determine_confirmation_type(
    scheduled_date: date,
    as_of_date: date,
    assume_auto_execution: bool,
    confirmation_rules: dict[str, Any],
    nav_available_for_date: bool,
    has_contradictory_evidence: bool,
) -> tuple[str, str, str]:
    """Determine confirmation type for a planned transaction.

    Returns (confirmation_type, confirmation_source, confidence).
    """
    settlement_days = confirmation_rules.get("settlement_days", 1)
    qdii_lag_days = confirmation_rules.get("qdii_lag_days", 0)
    require_nav = confirmation_rules.get("require_nav_available", True)
    require_no_contradiction = confirmation_rules.get("require_no_contradictory_evidence", True)
    expected_offset = confirmation_rules.get("expected_confirmation_date_offset_days", 3)

    total_lag = settlement_days + qdii_lag_days
    expected_confirmation_date = scheduled_date + timedelta(days=total_lag)
    max_confirmation_date = scheduled_date + timedelta(days=expected_offset)

    # Future scheduled date -> projected
    if scheduled_date > as_of_date:
        return "projected", "schedule", "projected"

    # Not auto-executed -> pending
    if not assume_auto_execution:
        return "pending_confirmation", "schedule", "pending"

    # Has contradictory evidence -> manual review
    if require_no_contradiction and has_contradictory_evidence:
        return "manual_review_required", "contradiction_detected", "ambiguous"

    # NAV not available yet -> pending
    if require_nav and not nav_available_for_date:
        if as_of_date >= max_confirmation_date:
            return "manual_review_required", "nav_unavailable_past_deadline", "low"
        return "pending_confirmation", "nav_not_yet_available", "pending"

    # Past expected confirmation date -> rule_confirmed
    if as_of_date >= expected_confirmation_date:
        return "rule_confirmed", "schedule_rule", "rule_confirmed_estimated"

    # Within settlement period -> pending
    return "pending_confirmation", "within_settlement", "pending"


def generate_planned_transactions(
    plan_data: dict[str, Any],
    as_of_date: date,
    nav_snapshot: dict[str, Any] | None = None,
    contradictory_evidence_funds: set[str] | None = None,
) -> dict[str, Any]:
    """Generate planned transactions from investment plan data.

    Args:
        plan_data: Parsed investment plan YAML data.
        as_of_date: The as-of date for determining confirmation status.
        nav_snapshot: Optional NAV snapshot for checking NAV availability.
        contradictory_evidence_funds: Fund codes with contradictory evidence.

    Returns:
        Dict with planned transactions and summary.
    """
    contra_funds = contradictory_evidence_funds or set()
    nav_data = nav_snapshot or {}
    nav_by_fund = nav_data.get("nav_by_fund", {})

    transactions = []
    plan_summaries = []

    for plan in plan_data.get("plans", []):
        plan_id = plan.get("plan_id", "unknown")
        fund_code = plan.get("fund_code", "")
        fund_name = plan.get("fund_name", "")
        amount = plan.get("amount", 0)
        schedule = plan.get("schedule", {})
        execution_policy = plan.get("execution_policy", {})
        fee_policy = plan.get("fee_policy", {})
        is_qdii = plan.get("is_qdii", False)

        frequency = schedule.get("frequency", "monthly")
        day_of_week = schedule.get("day_of_week")
        day_of_month = schedule.get("day_of_month")
        specific_date = _parse_date(schedule.get("specific_date"))
        start_date = _parse_date(schedule.get("start_date")) or as_of_date

        assume_auto = execution_policy.get("assume_auto_execution", False)
        confirmation_rules = execution_policy.get("confirmation_rules", {})
        skip_non_trading = execution_policy.get("skip_non_trading_days", True)
        next_trading_on_skip = execution_policy.get("next_trading_day_on_skip", True)

        # Generate all scheduled dates up to a reasonable horizon
        # For past dates, we generate up to as_of_date + small buffer
        horizon = as_of_date + timedelta(days=7)
        scheduled_dates = _generate_schedule_dates(
            frequency=frequency,
            start_date=start_date,
            end_date=horizon,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            specific_date=specific_date,
            skip_non_trading=skip_non_trading,
            next_trading_on_skip=next_trading_on_skip,
        )

        plan_txns = []
        for sched_date in scheduled_dates:
            # Check NAV availability for this date
            fund_nav_data = nav_by_fund.get(fund_code, {})
            nav_dates = fund_nav_data.get("nav_dates", [])
            nav_available = str(sched_date) in nav_dates if nav_dates else False
            # If no nav snapshot, assume NAV is available for past dates
            if not nav_snapshot and sched_date <= as_of_date:
                nav_available = True

            has_contra = fund_code in contra_funds

            conf_type, conf_source, confidence = _determine_confirmation_type(
                scheduled_date=sched_date,
                as_of_date=as_of_date,
                assume_auto_execution=assume_auto,
                confirmation_rules=confirmation_rules,
                nav_available_for_date=nav_available,
                has_contradictory_evidence=has_contra,
            )

            # Calculate fee
            sub_fee_rate = fee_policy.get("subscription_fee_rate")
            fee_discount = fee_policy.get("fee_discount_rate")
            fee_source = fee_policy.get("fee_source", "unknown")

            fee_amount = None
            net_amount = amount
            if sub_fee_rate is not None:
                gross_fee = amount * sub_fee_rate
                if fee_discount is not None:
                    gross_fee = gross_fee * fee_discount
                fee_amount = round(gross_fee, 2)
                net_amount = round(amount - fee_amount, 2)
            elif fee_source == "unknown":
                fee_amount = None
                net_amount = amount

            txn = {
                "transaction_id": f"plan_{plan_id}_{sched_date.isoformat()}",
                "source": "investment_plan",
                "plan_id": plan_id,
                "fund_code": fund_code,
                "fund_name": fund_name,
                "scheduled_date": sched_date.isoformat(),
                "action": "buy",
                "amount": amount,
                "net_amount": net_amount,
                "fee_amount": fee_amount,
                "fee_source": fee_source,
                "confirmation_type": conf_type,
                "confirmation_source": conf_source,
                "confidence": confidence,
                "is_qdii": is_qdii,
                "nav_available": nav_available,
            }
            transactions.append(txn)
            plan_txns.append(txn)

        plan_summaries.append({
            "plan_id": plan_id,
            "fund_code": fund_code,
            "frequency": frequency,
            "amount": amount,
            "assume_auto_execution": assume_auto,
            "total_scheduled": len(plan_txns),
            "evidence_confirmed": sum(1 for t in plan_txns if t["confirmation_type"] == "evidence_confirmed"),
            "rule_confirmed": sum(1 for t in plan_txns if t["confirmation_type"] == "rule_confirmed"),
            "pending_confirmation": sum(1 for t in plan_txns if t["confirmation_type"] == "pending_confirmation"),
            "projected": sum(1 for t in plan_txns if t["confirmation_type"] == "projected"),
            "manual_review_required": sum(1 for t in plan_txns if t["confirmation_type"] == "manual_review_required"),
        })

    return {
        "schema_version": "planned_transactions.v1",
        "source": "investment_plan",
        "as_of_date": as_of_date.isoformat(),
        "total_transactions": len(transactions),
        "transactions": transactions,
        "plan_summaries": plan_summaries,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate planned transactions from investment plan")
    parser.add_argument("--plan", required=True, help="Path to investment plan YAML")
    parser.add_argument("--nav-snapshot", default=None, help="Path to NAV snapshot JSON")
    parser.add_argument("--as-of-date", required=True, help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Output path for planned transactions JSON")
    args = parser.parse_args()

    if yaml is None:
        print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    with open(args.plan, encoding="utf-8") as f:
        plan_data = yaml.safe_load(f)

    nav_snapshot = None
    if args.nav_snapshot:
        with open(args.nav_snapshot, encoding="utf-8") as f:
            nav_snapshot = json.load(f)

    as_of_date = date.fromisoformat(args.as_of_date)

    result = generate_planned_transactions(
        plan_data=plan_data,
        as_of_date=as_of_date,
        nav_snapshot=nav_snapshot,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "total_transactions": result["total_transactions"],
        "plan_summaries": result["plan_summaries"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
