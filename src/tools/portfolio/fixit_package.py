"""Fix-it package generator — M7.9.

Generates diagnostic CSV/JSON files listing missing data that prevents
full transaction-derived reconstruction. Users can fill these in to
improve reconstruction quality.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def generate_fixit_package(
    positions: list[dict[str, Any]],
    output_dir: Path,
    identity_resolutions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate fix-it package from position reconstruction data.

    Outputs:
    - missing_trade_nav.csv: Transactions missing trade-date NAV
    - missing_fee_rules.csv: Funds missing fee schedules
    - unmatched_refunds.csv: Refunds that couldn't be matched
    - conversion_review_needed.csv: Conversions needing review
    - identity_candidates.private.csv: M7.11 name search candidates for unverified funds
    - reconstruction_quality_summary.json: Per-position quality summary

    Args:
        positions: List of position dicts with reconstruction data.
        output_dir: Directory to write fix-it files.
        identity_resolutions: List of identity resolution dicts (M7.11).

    Returns:
        Summary dict with file paths and counts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    missing_nav_rows = []
    missing_fee_rows = []
    unmatched_refund_rows = []
    conversion_review_rows = []
    identity_candidate_rows = []
    quality_summary = []

    for pos in positions:
        fund_code = pos.get("fund_code", "")
        fund_name = pos.get("fund_name", pos.get("raw_fund_name", ""))
        blockers = pos.get("reconstruction_blockers", [])

        # Missing trade NAV
        if "missing_trade_nav" in blockers:
            missing_nav_rows.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "trade_nav_missing_count": pos.get("trade_nav_missing_count", ""),
                "trade_nav_coverage_ratio": pos.get("trade_nav_coverage_ratio", ""),
            })

        # Missing fee
        if "missing_fee" in blockers:
            missing_fee_rows.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "fee_schedule_status": pos.get("fee_schedule_status", "unavailable"),
            })

        # Unmatched refunds
        if pos.get("unmatched_refund_count", 0) > 0:
            unmatched_refund_rows.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "unmatched_refund_count": pos.get("unmatched_refund_count", 0),
            })

        # Conversion review
        if "conversion_unverified" in blockers:
            conversion_review_rows.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "conversion_count": pos.get("conversion_count", 0),
            })

        # Quality summary
        quality_summary.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "reconstruction_quality": pos.get("reconstruction_quality", ""),
            "holdings_source": pos.get("holdings_source", ""),
            "valuation_source": pos.get("valuation_source", ""),
            "units_coverage_ratio": pos.get("units_coverage_ratio", ""),
            "reconstruction_blockers": ",".join(blockers) if blockers else "",
            "total_units": pos.get("total_units") or pos.get("units", ""),
            "current_value": pos.get("current_value", ""),
            "identity_verification_status": pos.get("identity_verification_status", ""),
        })

    # M7.11: Identity candidates from name search
    if identity_resolutions:
        for res in identity_resolutions:
            ivs = res.get("identity_verification_status", "")
            if ivs in ("name_search_candidate_unverified", "name_only", "code_unverified"):
                raw_name = res.get("raw_fund_name") or res.get("fund_name", "")
                resolved_code = res.get("resolved_fund_code", "")
                # Add unverified fund as a row
                identity_candidate_rows.append({
                    "raw_fund_name": raw_name,
                    "normalized_name": res.get("normalized_name", ""),
                    "resolved_fund_code": resolved_code or "",
                    "identity_verification_status": ivs,
                    "action": "verify_fund_code",
                    "suggested_fund_code": "",
                    "suggested_fund_name": "",
                    "match_score": "",
                    "match_bucket": "",
                    "verified_by_user": "",
                    "verification_source": "",
                })
                # Add candidate codes from name search
                for cand in res.get("name_search_candidates", []):
                    identity_candidate_rows.append({
                        "raw_fund_name": raw_name,
                        "normalized_name": res.get("normalized_name", ""),
                        "resolved_fund_code": resolved_code or "",
                        "identity_verification_status": ivs,
                        "action": "review_candidate",
                        "suggested_fund_code": cand.get("fund_code", ""),
                        "suggested_fund_name": cand.get("fund_name", ""),
                        "match_score": cand.get("match_score", ""),
                        "match_bucket": cand.get("match_bucket", ""),
                        "verified_by_user": "",
                        "verification_source": "",
                    })

    # Write CSVs
    files_written = {}

    if missing_nav_rows:
        path = output_dir / "missing_trade_nav.csv"
        _write_csv(path, missing_nav_rows)
        files_written["missing_trade_nav"] = str(path)

    if missing_fee_rows:
        path = output_dir / "missing_fee_rules.csv"
        _write_csv(path, missing_fee_rows)
        files_written["missing_fee_rules"] = str(path)

    if unmatched_refund_rows:
        path = output_dir / "unmatched_refunds.csv"
        _write_csv(path, unmatched_refund_rows)
        files_written["unmatched_refunds"] = str(path)

    if conversion_review_rows:
        path = output_dir / "conversion_review_needed.csv"
        _write_csv(path, conversion_review_rows)
        files_written["conversion_review_needed"] = str(path)

    # M7.11: Identity candidates CSV
    if identity_candidate_rows:
        path = output_dir / "identity_candidates.private.csv"
        _write_csv(path, identity_candidate_rows)
        files_written["identity_candidates"] = str(path)

    # Write quality summary JSON
    path = output_dir / "reconstruction_quality_summary.json"
    path.write_text(
        json.dumps(quality_summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    files_written["reconstruction_quality_summary"] = str(path)

    return {
        "files_written": files_written,
        "missing_trade_nav_count": len(missing_nav_rows),
        "missing_fee_rules_count": len(missing_fee_rows),
        "unmatched_refunds_count": len(unmatched_refund_rows),
        "conversion_review_count": len(conversion_review_rows),
        "identity_candidate_count": len(identity_candidate_rows),
        "total_positions": len(positions),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of dicts to CSV."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
