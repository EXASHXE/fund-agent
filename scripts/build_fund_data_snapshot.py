#!/usr/bin/env python3
"""Build fund data snapshots: NAV, profile, holdings, benchmark, fee schedule.

Uses host-layer provider adapters (AkShare/Eastmoney) for live data.
Lazy imports only. Graceful degradation when providers unavailable.

Usage:
    python scripts/build_fund_data_snapshot.py \
        --fund-codes 017436 008253 378006 001198 \
        --as-of-date 2025-05-19 \
        --output-dir private_data

Outputs:
    - nav_snapshot.private.json
    - fund_profile_snapshot.private.json
    - fee_schedule_snapshot.private.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

RUN_LIVE = os.environ.get("RUN_LIVE_PROVIDER_TESTS", "0") == "1"


def _parse_date(val) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _try_akshare_nav(fund_code: str, start: str, end: str) -> dict[str, Any] | None:
    """Try to fetch NAV history via AkShare. Returns None if unavailable."""
    if not RUN_LIVE:
        return None
    try:
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter
        adapter = AkShareAdapter()
        result = adapter.get_fund_nav_history(fund_code, start, end)
        if result.ok and result.data:
            records = []
            for r in result.data:
                nav_date = r.get("净值日期") or r.get("date")
                nav_val = r.get("单位净值") or r.get("nav")
                if nav_date and nav_val is not None:
                    records.append({"date": str(nav_date), "nav": float(nav_val)})
            return {"provider": "akshare", "records": records}
    except Exception:
        pass
    return None


def _try_akshare_profile(fund_code: str) -> dict[str, Any] | None:
    """Try to fetch fund profile via AkShare."""
    if not RUN_LIVE:
        return None
    try:
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter
        adapter = AkShareAdapter()
        result = adapter.get_fund_profile(fund_code)
        if result.ok and result.data:
            return {"provider": "akshare", **result.data}
    except Exception:
        pass
    return None


def build_nav_snapshot(
    fund_codes: list[str],
    as_of_date: date,
    nav_overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Build NAV snapshot for given fund codes.

    Args:
        fund_codes: List of fund codes to fetch NAV for.
        as_of_date: The as-of date.
        nav_overrides: Optional manual NAV data {fund_code: {date_str: nav_value}}.

    Returns:
        NAV snapshot dict.
    """
    overrides = nav_overrides or {}
    nav_by_fund = {}
    start = (as_of_date - timedelta(days=30)).isoformat()
    end = as_of_date.isoformat()

    for fc in fund_codes:
        # Try provider first
        provider_data = _try_akshare_nav(fc, start, end)

        if provider_data:
            nav_by_fund[fc] = {
                "provider": provider_data["provider"],
                "records": provider_data["records"],
                "nav_dates": [r["date"] for r in provider_data["records"]],
            }
        elif fc in overrides:
            # Use manual overrides
            records = [{"date": d, "nav": v} for d, v in sorted(overrides[fc].items())]
            nav_by_fund[fc] = {
                "provider": "manual_override",
                "records": records,
                "nav_dates": [r["date"] for r in records],
            }
        else:
            nav_by_fund[fc] = {
                "provider": "unavailable",
                "records": [],
                "nav_dates": [],
                "warnings": ["NAV data not available from any source"],
            }

    return {
        "schema_version": "nav_snapshot.v1",
        "as_of_date": as_of_date.isoformat(),
        "captured_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "nav_by_fund": nav_by_fund,
        "limitations": ["NAV data depends on provider availability; manual overrides take priority when provided"],
    }


def build_fund_profile_snapshot(
    fund_codes: list[str],
    as_of_date: date,
    profile_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build fund profile snapshot for given fund codes."""
    overrides = profile_overrides or {}
    fund_profiles = {}
    fund_holdings_data = {}
    benchmark_info = {}

    for fc in fund_codes:
        if fc in overrides:
            p = overrides[fc]
            fund_profiles[fc] = {
                "fund_code": fc,
                "fund_name": p.get("fund_name"),
                "fund_type": p.get("fund_type"),
                "manager": p.get("manager"),
                "benchmark": p.get("benchmark"),
                "tracking_index": p.get("tracking_index"),
                "inception_date": p.get("inception_date"),
                "size_category": p.get("size_category"),
                "tags": p.get("tags", []),
                "provenance": {"source": "manual_override"},
            }
            if p.get("holdings"):
                fund_holdings_data[fc] = {
                    "fund_code": fc,
                    "as_of": as_of_date.isoformat(),
                    "holdings": p["holdings"],
                    "provenance": {"source": "manual_override"},
                }
            if p.get("benchmark_symbol"):
                benchmark_info[p["benchmark_symbol"]] = {
                    "symbol": p["benchmark_symbol"],
                    "name": p.get("benchmark_name", ""),
                    "provider": p.get("benchmark_provider", "unknown"),
                    "asset_class": p.get("asset_class"),
                }
        else:
            # Try provider
            provider_data = _try_akshare_profile(fc)
            if provider_data:
                fund_profiles[fc] = {
                    "fund_code": fc,
                    **provider_data,
                    "provenance": {"source": "akshare"},
                }
            else:
                fund_profiles[fc] = {
                    "fund_code": fc,
                    "fund_name": None,
                    "provenance": {"source": "unavailable"},
                    "warnings": ["Profile data not available from any source"],
                }

    return {
        "schema_version": "fund_profile_snapshot.v1",
        "as_of_date": as_of_date.isoformat(),
        "fund_profiles": fund_profiles,
        "fund_holdings": fund_holdings_data,
        "benchmark_info": benchmark_info,
        "limitations": ["Profile data depends on provider availability"],
    }


def build_fee_schedule_snapshot(
    fund_codes: list[str],
    as_of_date: date,
    fee_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build fee schedule snapshot for given fund codes."""
    overrides = fee_overrides or {}
    fee_schedules = {}

    for fc in fund_codes:
        if fc in overrides:
            fee_schedules[fc] = {
                "fund_code": fc,
                **overrides[fc],
                "provenance": {"source": "manual_override"},
            }
        else:
            fee_schedules[fc] = {
                "fund_code": fc,
                "purchase_fee": None,
                "redemption_fee_tiers": [],
                "provenance": {"source": "unavailable"},
                "warnings": ["Fee schedule not available"],
            }

    return {
        "schema_version": "fee_schedule_snapshot.v1",
        "as_of_date": as_of_date.isoformat(),
        "fee_schedules": fee_schedules,
        "limitations": ["Fee data depends on provider availability; defaults may not match actual fund terms"],
    }


def main():
    parser = argparse.ArgumentParser(description="Build fund data snapshots")
    parser.add_argument("--fund-codes", nargs="+", required=True, help="Fund codes to fetch")
    parser.add_argument("--as-of-date", required=True, help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", required=True, help="Output directory for snapshot files")
    parser.add_argument("--nav-overrides", default=None, help="Path to NAV overrides JSON")
    parser.add_argument("--profile-overrides", default=None, help="Path to profile overrides JSON")
    parser.add_argument("--fee-overrides", default=None, help="Path to fee overrides JSON")
    args = parser.parse_args()

    as_of_date = date.fromisoformat(args.as_of_date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nav_overrides = None
    if args.nav_overrides:
        with open(args.nav_overrides, encoding="utf-8") as f:
            nav_overrides = json.load(f)

    profile_overrides = None
    if args.profile_overrides:
        with open(args.profile_overrides, encoding="utf-8") as f:
            profile_overrides = json.load(f)

    fee_overrides = None
    if args.fee_overrides:
        with open(args.fee_overrides, encoding="utf-8") as f:
            fee_overrides = json.load(f)

    nav_snapshot = build_nav_snapshot(args.fund_codes, as_of_date, nav_overrides)
    profile_snapshot = build_fund_profile_snapshot(args.fund_codes, as_of_date, profile_overrides)
    fee_snapshot = build_fee_schedule_snapshot(args.fund_codes, as_of_date, fee_overrides)

    for name, data in [
        ("nav_snapshot.private.json", nav_snapshot),
        ("fund_profile_snapshot.private.json", profile_snapshot),
        ("fee_schedule_snapshot.private.json", fee_snapshot),
    ]:
        out_path = output_dir / name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Wrote {out_path}")

    print(f"Snapshots built for {len(args.fund_codes)} funds as of {as_of_date}")


if __name__ == "__main__":
    main()
