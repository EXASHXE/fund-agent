#!/usr/bin/env python3
"""Resolve fund identities from plan codes, manual overrides, and optional provider search.

Uses plan fund_code first, manual override second, provider search optional.
No ambiguous guessing. Outputs candidate audit trail.

Usage:
    python scripts/resolve_fund_identities.py \
        --ledger private_data/transaction_ledger.private.json \
        --plan private_data/investment_plan.private.yaml \
        --output private_data/fund_identity_resolution.private.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.fund_identity_utils import coerce_fund_code, is_valid_fund_code, normalize_fund_name

try:
    import yaml
except ImportError:
    yaml = None


def _load_overrides(overrides_path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Load manual fund identity overrides from a YAML file.

    Returns a tuple of:
    - lookup dict mapping various lookup keys to override records
    - list of validation warnings for invalid override entries
    """
    if yaml is None:
        print("Warning: PyYAML not installed, skipping overrides", file=__import__("sys").stderr)
        return {}, []
    try:
        with open(overrides_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, ValueError) as exc:
        print(f"Warning: cannot read overrides file: {exc}", file=__import__("sys").stderr)
        return {}, []

    if not data or not isinstance(data, dict):
        return {}, []

    lookup: dict[str, dict[str, Any]] = {}
    validation_warnings: list[str] = []

    # Process funds list
    for entry in data.get("funds", []):
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("raw_name", "")
        fund_code = str(entry.get("fund_code", ""))
        fund_name = entry.get("fund_name", "")
        if not raw_name or not fund_code:
            continue
        if not is_valid_fund_code(fund_code):
            validation_warnings.append(
                f"Override fund_code '{fund_code}' for raw_name '{raw_name}' is not a valid six-digit code; skipped"
            )
            continue
        record = {"fund_code": fund_code, "fund_name": fund_name or raw_name}
        # Index by raw_name and normalized variants
        lookup[raw_name] = record
        lookup[normalize_fund_name(raw_name)] = record

    # Process aliases
    for alias, fund_code in data.get("aliases", {}).items():
        if not alias or not fund_code:
            continue
        fund_code_str = str(fund_code)
        if not is_valid_fund_code(fund_code_str):
            validation_warnings.append(
                f"Override alias '{alias}' fund_code '{fund_code_str}' is not a valid six-digit code; skipped"
            )
            continue
        record = {"fund_code": fund_code_str, "fund_name": alias}
        lookup[alias] = record
        lookup[normalize_fund_name(alias)] = record

    return lookup, validation_warnings



def _compute_resolution_status(
    resolved_code: str | None,
    resolution_source: str,
    ref_info: dict[str, Any],
) -> str:
    """Compute resolution_status for a fund resolution entry.

    Returns one of: valid_code, manual_override, name_only, invalid_code, unresolved.
    """
    if resolution_source == "manual_override":
        return "manual_override"
    if resolved_code is not None:
        return "valid_code"
    # resolved_code is None — check why
    if ref_info.get("resolved_by_name"):
        return "name_only"
    raw_fc = ref_info.get("fund_code")
    if raw_fc is not None and not is_valid_fund_code(raw_fc):
        return "invalid_code"
    return "unresolved"


def resolve_fund_identities(
    ledger_data: dict[str, Any] | None = None,
    plan_data: dict[str, Any] | None = None,
    manual_overrides: dict[str, str] | None = None,
    override_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve fund identities from available sources.

    Priority:
    1. Plan fund_code (from investment plan)
    2. Manual override (from override file or dict)
    3. Alipay fund_code (from transaction)
    4. Unresolved (no guessing)

    Args:
        ledger_data: Transaction ledger with fund_code fields.
        plan_data: Investment plan with known fund_codes.
        manual_overrides: Manual fund_code mappings {raw_name: resolved_code}.
        override_lookup: Pre-processed override lookup from YAML file.

    Returns:
        Fund identity resolution with audit trail.
    """
    overrides = manual_overrides or {}
    ov_lookup = override_lookup or {}
    plan_funds: dict[str, dict[str, Any]] = {}

    # Index plan funds
    if plan_data:
        for plan in plan_data.get("plans", []):
            fc = plan.get("fund_code")
            if fc:
                plan_funds[fc] = {
                    "fund_code": fc,
                    "fund_name": plan.get("fund_name"),
                    "source": "investment_plan",
                    "plan_id": plan.get("plan_id"),
                }

    # Collect all fund references from ledger
    fund_refs: dict[str, dict[str, Any]] = {}
    if ledger_data:
        for txn in ledger_data.get("transactions", []):
            fc = txn.get("fund_code")
            fn = txn.get("fund_name")
            # Use fund_code as key when available, otherwise use fund_name
            ref_key = fc or fn
            if ref_key and ref_key not in fund_refs:
                fund_refs[ref_key] = {
                    "fund_code": fc,
                    "fund_name": fn,
                    "source": "transaction_ledger",
                    "seen_in_alipay": txn.get("source") == "alipay",
                    "seen_in_plan": txn.get("source") == "investment_plan",
                    "resolved_by_name": fc is None and fn is not None,
                }

    # Resolve each fund
    resolutions = []
    all_fund_codes = set(fund_refs.keys()) | set(plan_funds.keys())

    for fund_key in sorted(all_fund_codes):
        plan_info = plan_funds.get(fund_key, {})
        ref_info = fund_refs.get(fund_key, {})
        override_code = overrides.get(fund_key) or overrides.get(ref_info.get("fund_name", ""))

        # Check override_lookup (from YAML file) by fund_key, fund_name, and normalized variants
        ov_record = None
        fund_name = ref_info.get("fund_name") or plan_info.get("fund_name") or ""
        for lookup_key in (fund_key, fund_name, normalize_fund_name(fund_key), normalize_fund_name(fund_name)):
            if lookup_key and lookup_key in ov_lookup:
                ov_record = ov_lookup[lookup_key]
                break
        if ov_record and ov_record.get("fund_code"):
            override_code = ov_record["fund_code"]

        candidates = []
        # CRITICAL: resolved_fund_code must be a valid six-digit code or None.
        # Never let a Chinese name or other non-code value leak in.
        raw_fund_code = ref_info.get("fund_code")
        raw_fund_name = ref_info.get("fund_name") or plan_info.get("fund_name")
        resolved_code = coerce_fund_code(raw_fund_code) or coerce_fund_code(fund_key)
        resolution_source = "transaction_ledger"
        confidence = "high"
        audit_steps = []

        # Step 1: Plan fund_code
        if plan_info:
            candidates.append({"code": fund_key, "name": plan_info.get("fund_name"), "source": "investment_plan"})
            resolution_source = "investment_plan"
            audit_steps.append({"step": "plan_fund_code", "code": fund_key, "source": "plan_id=" + str(plan_info.get("plan_id", ""))})

        # Step 2: Manual override
        if override_code and override_code != resolved_code:
            candidates.append({"code": override_code, "source": "manual_override"})
            resolved_code = override_code
            resolution_source = "manual_override"
            confidence = "high"
            audit_steps.append({"step": "manual_override", "from": fund_key, "to": override_code})

        # Step 3: Transaction ledger
        if ref_info:
            candidates.append({"code": resolved_code, "name": ref_info.get("fund_name"), "source": "transaction_ledger"})
            if not plan_info and not override_code:
                resolution_source = "transaction_ledger"
                # Name-only resolution is lower confidence
                if ref_info.get("resolved_by_name"):
                    confidence = "low"
                    audit_steps.append({
                        "step": "ledger_reference_by_name",
                        "fund_name": ref_info.get("fund_name"),
                        "note": "fund_code absent; resolved by fund_name only",
                    })
                else:
                    confidence = "medium" if ref_info.get("seen_in_alipay") else "low"
            audit_steps.append({
                "step": "ledger_reference",
                "code": resolved_code,
                "alipay": ref_info.get("seen_in_alipay", False),
                "plan": ref_info.get("seen_in_plan", False),
            })

        # Compute resolution_status
        resolution_status = _compute_resolution_status(resolved_code, resolution_source, ref_info)

        resolutions.append({
            "resolved_fund_code": resolved_code,
            "raw_reference": fund_key,
            "raw_fund_code": raw_fund_code,
            "raw_fund_name": raw_fund_name,
            "normalized_name": normalize_fund_name(raw_fund_name) if raw_fund_name else None,
            "fund_name": raw_fund_name,
            "resolution_source": resolution_source,
            "resolution_status": resolution_status,
            "confidence": confidence,
            "candidates": candidates,
            "audit_trail": audit_steps,
        })

    summary = {
        "total_funds": len(resolutions),
        "valid_fund_codes_count": sum(1 for r in resolutions if r["resolved_fund_code"] is not None),
        "name_only_count": sum(1 for r in resolutions if r["resolution_status"] == "name_only"),
        "high_confidence": sum(1 for r in resolutions if r["confidence"] == "high"),
        "medium_confidence": sum(1 for r in resolutions if r["confidence"] == "medium"),
        "low_confidence_count": sum(1 for r in resolutions if r["confidence"] == "low"),
        "unresolved_count": sum(1 for r in resolutions if r["resolution_source"] == "none"),
        "manual_overrides_used": bool(ov_lookup or overrides),
        "manual_override_matches_count": sum(1 for r in resolutions if r["resolution_source"] == "manual_override"),
        "resolution_status_counts": {
            "valid_code": sum(1 for r in resolutions if r["resolution_status"] == "valid_code"),
            "manual_override": sum(1 for r in resolutions if r["resolution_status"] == "manual_override"),
            "name_only": sum(1 for r in resolutions if r["resolution_status"] == "name_only"),
            "invalid_code": sum(1 for r in resolutions if r["resolution_status"] == "invalid_code"),
            "unresolved": sum(1 for r in resolutions if r["resolution_status"] == "unresolved"),
        },
    }

    return {
        "schema_version": "fund_identity_resolution.v2",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "resolutions": resolutions,
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve fund identities")
    parser.add_argument("--ledger", default=None, help="Path to transaction ledger JSON")
    parser.add_argument("--plan", default=None, help="Path to investment plan YAML")
    parser.add_argument("--overrides", default=None, help="Path to fund identity overrides YAML")
    parser.add_argument("--output", required=True, help="Output path for fund identity resolution JSON")
    args = parser.parse_args()

    ledger_data = None
    if args.ledger:
        with open(args.ledger, encoding="utf-8") as f:
            ledger_data = json.load(f)

    plan_data = None
    if args.plan:
        if yaml is None:
            print("Warning: PyYAML not installed, skipping plan", file=__import__("sys").stderr)
        else:
            with open(args.plan, encoding="utf-8") as f:
                plan_data = yaml.safe_load(f)

    override_lookup = {}
    override_warnings: list[str] = []
    if args.overrides:
        override_lookup, override_warnings = _load_overrides(Path(args.overrides))
        for w in override_warnings:
            print(f"Warning: {w}", file=__import__("sys").stderr)

    result = resolve_fund_identities(
        ledger_data=ledger_data,
        plan_data=plan_data,
        override_lookup=override_lookup,
    )

    # Include override validation warnings in summary
    if override_warnings:
        result["summary"]["override_validation_warnings"] = override_warnings

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
