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

try:
    import yaml
except ImportError:
    yaml = None


def resolve_fund_identities(
    ledger_data: dict[str, Any] | None = None,
    plan_data: dict[str, Any] | None = None,
    manual_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve fund identities from available sources.

    Priority:
    1. Plan fund_code (from investment plan)
    2. Manual override
    3. Alipay fund_code (from transaction)
    4. Unresolved (no guessing)

    Args:
        ledger_data: Transaction ledger with fund_code fields.
        plan_data: Investment plan with known fund_codes.
        manual_overrides: Manual fund_code mappings {raw_name: resolved_code}.

    Returns:
        Fund identity resolution with audit trail.
    """
    overrides = manual_overrides or {}
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
            if fc and fc not in fund_refs:
                fund_refs[fc] = {
                    "fund_code": fc,
                    "fund_name": fn,
                    "source": "transaction_ledger",
                    "seen_in_alipay": txn.get("source") == "alipay",
                    "seen_in_plan": txn.get("source") == "investment_plan",
                }

    # Resolve each fund
    resolutions = []
    all_fund_codes = set(fund_refs.keys()) | set(plan_funds.keys())

    for fund_code in sorted(all_fund_codes):
        plan_info = plan_funds.get(fund_code, {})
        ref_info = fund_refs.get(fund_code, {})
        override_code = overrides.get(fund_code) or overrides.get(ref_info.get("fund_name", ""))

        candidates = []
        resolved_code = fund_code
        resolution_source = "transaction_ledger"
        confidence = "high"
        audit_steps = []

        # Step 1: Plan fund_code
        if plan_info:
            candidates.append({"code": fund_code, "name": plan_info.get("fund_name"), "source": "investment_plan"})
            resolution_source = "investment_plan"
            audit_steps.append({"step": "plan_fund_code", "code": fund_code, "source": "plan_id=" + str(plan_info.get("plan_id", ""))})

        # Step 2: Manual override
        if override_code and override_code != fund_code:
            candidates.append({"code": override_code, "source": "manual_override"})
            resolved_code = override_code
            resolution_source = "manual_override"
            confidence = "high"
            audit_steps.append({"step": "manual_override", "from": fund_code, "to": override_code})

        # Step 3: Transaction ledger
        if ref_info:
            candidates.append({"code": fund_code, "name": ref_info.get("fund_name"), "source": "transaction_ledger"})
            if not plan_info and not override_code:
                resolution_source = "transaction_ledger"
                confidence = "medium" if ref_info.get("seen_in_alipay") else "low"
            audit_steps.append({
                "step": "ledger_reference",
                "code": fund_code,
                "alipay": ref_info.get("seen_in_alipay", False),
                "plan": ref_info.get("seen_in_plan", False),
            })

        resolutions.append({
            "resolved_fund_code": resolved_code,
            "fund_name": ref_info.get("fund_name") or plan_info.get("fund_name"),
            "resolution_source": resolution_source,
            "confidence": confidence,
            "candidates": candidates,
            "audit_trail": audit_steps,
        })

    summary = {
        "total_funds": len(resolutions),
        "high_confidence": sum(1 for r in resolutions if r["confidence"] == "high"),
        "medium_confidence": sum(1 for r in resolutions if r["confidence"] == "medium"),
        "low_confidence": sum(1 for r in resolutions if r["confidence"] == "low"),
        "unresolved": sum(1 for r in resolutions if r["resolution_source"] == "none"),
    }

    return {
        "schema_version": "fund_identity_resolution.v1",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "resolutions": resolutions,
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve fund identities")
    parser.add_argument("--ledger", default=None, help="Path to transaction ledger JSON")
    parser.add_argument("--plan", default=None, help="Path to investment plan YAML")
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

    result = resolve_fund_identities(
        ledger_data=ledger_data,
        plan_data=plan_data,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
