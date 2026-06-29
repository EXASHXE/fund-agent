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

# M7.6: Allowed verification sources for verified_by_user
ALLOWED_VERIFICATION_SOURCES = frozenset({
    "alipay_holdings_page",
    "fund_detail_page",
    "official_fund_statement",
    "provider_cross_check",
    "user_manual_verified",
    "provider_name_search",
})

# M7.11: Identity verification statuses that indicate name-only resolution
# (no fund_code from plan, override, or transaction ledger)
_NAME_ONLY_STATUSES = frozenset({
    "name_only",
    "code_unverified",
})

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
        record = {
            "fund_code": fund_code,
            "fund_name": fund_name or raw_name,
            "verified_by_user": bool(entry.get("verified_by_user", False)),
            "verified_at": entry.get("verified_at"),
            "verification_source": entry.get("verification_source"),
        }
        # M7.6: Validate verified_by_user — if missing required fields, downgrade
        if record["verified_by_user"]:
            missing = []
            if not record.get("verification_source") or record["verification_source"] not in ALLOWED_VERIFICATION_SOURCES:
                missing.append("verification_source")
            if not record.get("verified_at"):
                missing.append("verified_at")
            if missing:
                validation_warnings.append(
                    f"Override for raw_name '{raw_name}' has verified_by_user:true but missing {', '.join(missing)}; "
                    f"downgrading to unverified"
                )
                record["verified_by_user"] = False
                record["_downgrade_reason"] = f"missing {', '.join(missing)}"
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



def _compute_identity_verification_status(
    resolved_code: str | None,
    resolution_status: str,
    ref_info: dict[str, Any],
    override_record: dict[str, Any] | None = None,
    provider_lookup_result: str | None = None,
    name_search_result: str | None = None,
) -> str:
    """Compute identity_verification_status for a fund resolution entry.

    Returns one of: verified, provider_verified, user_verified_override,
    manual_override_unverified, code_name_mismatch, provider_lookup_failed,
    code_unverified, name_only, invalid_code, name_search_candidate_unverified.

    M7.4: manual_override no longer auto-elevates to override_verified.
    Without provider cross-check or explicit user verification, manual
    overrides default to manual_override_unverified.

    M7.6: verified_by_user:true is NOT an unlock switch. It requires
    fund_code (6-digit), fund_name, verification_source (in allowed set),
    and verified_at. Missing fields cause downgrade to manual_override_unverified.

    M7.11: name_search_result can be "auto_verified" (→ provider_verified),
    "candidate_unverified" (→ name_search_candidate_unverified), or None.
    """
    # Invalid code → invalid_code
    if resolution_status == "invalid_code":
        return "invalid_code"

    # M7.11: Name search auto-verified → provider_verified
    if name_search_result == "auto_verified":
        return "provider_verified"

    # M7.11: Name search found candidates but couldn't auto-verify
    if name_search_result == "candidate_unverified":
        return "name_search_candidate_unverified"

    # Name-only → name_only
    if resolution_status == "name_only":
        return "name_only"

    # Manual override with valid code — requires verification
    if resolution_status == "manual_override" and resolved_code is not None:
        # Provider cross-check takes priority
        if provider_lookup_result == "confirmed":
            return "provider_verified"
        if provider_lookup_result == "mismatch":
            return "code_name_mismatch"
        if provider_lookup_result == "failed":
            # Provider unavailable — check user verification
            override_verified_by_user = bool(override_record.get("verified_by_user", False)) if override_record else False
            if override_verified_by_user:
                return "user_verified_override"
            return "provider_lookup_failed"
        # No provider attempted — check user verification
        override_verified_by_user = bool(override_record.get("verified_by_user", False)) if override_record else False
        if override_verified_by_user:
            return "user_verified_override"
        return "manual_override_unverified"

    # Unresolved → code_unverified
    if resolved_code is None:
        return "code_unverified"

    # valid_code: check for code/name mismatch
    # A mismatch occurs when the resolved fund_code does not match the
    # fund_name in the override record (i.e., the override mapped a name
    # to a different code than what the data originally contained).
    raw_code = ref_info.get("fund_code")
    if raw_code is not None and str(raw_code) != str(resolved_code):
        # The code was changed by override or plan — check if names match
        override_name = override_record.get("fund_name") if override_record else None
        raw_name = ref_info.get("fund_name")
        if override_name and raw_name and normalize_fund_name(override_name) != normalize_fund_name(raw_name):
            return "code_name_mismatch"

    # If we have a valid code from the transaction source (no override needed)
    if resolution_status == "valid_code":
        return "verified"

    # Fallback
    return "code_unverified"


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
    name_search_provider: Any | None = None,
    enable_name_search: bool = False,
) -> dict[str, Any]:
    """Resolve fund identities from available sources.

    Priority:
    1. Plan fund_code (from investment plan)
    2. Manual override (from override file or dict)
    3. Provider name search discovery (M7.11, only when enable_name_search=True)
    4. Alipay fund_code (from transaction)
    5. Unresolved (no guessing)

    M7.11: When enable_name_search=True and a name_search_provider is given,
    funds with no code from plan/override/transaction are searched by name.
    Only unique high-confidence matches auto-promote to provider_verified.
    Ambiguous/low-confidence candidates stay as name_search_candidate_unverified.

    Args:
        ledger_data: Transaction ledger with fund_code fields.
        plan_data: Investment plan with known fund_codes.
        manual_overrides: Manual fund_code mappings {raw_name: resolved_code}.
        override_lookup: Pre-processed override lookup from YAML file.
        name_search_provider: FundIdentitySearchProvider instance (M7.11).
        enable_name_search: Whether to enable name search discovery (M7.11).

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

        # Step 2.5: Provider name search discovery (M7.11)
        # Only attempt when no code from plan, override, or transaction
        name_search_result = None
        name_search_candidates_data = None
        if (
            enable_name_search
            and name_search_provider is not None
            and resolved_code is None
            and raw_fund_name
        ):
            from src.tools.portfolio.fund_identity_candidate_discovery import (
                discover_candidates,
                should_auto_verify,
                extract_fund_name_from_alipay_item,
            )
            # Extract normalized name from raw Alipay name
            extracted = extract_fund_name_from_alipay_item(raw_fund_name)
            norm_name = extracted["normalized_name"]
            if norm_name:
                discovery = discover_candidates([raw_fund_name], provider=name_search_provider)
                scored_candidates = discovery.get(norm_name, [])
                if scored_candidates:
                    name_search_candidates_data = [
                        {
                            "fund_code": c.fund_code,
                            "fund_name": c.fund_name,
                            "match_score": c.match_score,
                            "match_bucket": c.match_bucket,
                            "match_reasons": c.match_reasons,
                            "risk_flags": c.risk_flags,
                        }
                        for c in scored_candidates
                    ]
                    can_auto_verify, verify_reason = should_auto_verify(scored_candidates)
                    if can_auto_verify:
                        top = scored_candidates[0]
                        resolved_code = top.fund_code
                        resolution_source = "name_search_auto_verified"
                        confidence = "medium"
                        name_search_result = "auto_verified"
                        audit_steps.append({
                            "step": "name_search_auto_verified",
                            "fund_code": top.fund_code,
                            "fund_name": top.fund_name,
                            "match_score": top.match_score,
                            "match_bucket": top.match_bucket,
                            "verify_reason": verify_reason,
                        })
                    else:
                        name_search_result = "candidate_unverified"
                        audit_steps.append({
                            "step": "name_search_candidate_unverified",
                            "candidate_count": len(scored_candidates),
                            "top_score": scored_candidates[0].match_score,
                            "verify_reason": verify_reason,
                            "note": "candidates found but auto-verify conditions not met; manual verification required",
                        })

        # Step 3: Transaction ledger
        if ref_info:
            candidates.append({"code": resolved_code, "name": ref_info.get("fund_name"), "source": "transaction_ledger"})
            if not plan_info and not override_code and name_search_result is None:
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

        # Compute identity_verification_status
        identity_verification_status = _compute_identity_verification_status(
            resolved_code=resolved_code,
            resolution_status=resolution_status,
            ref_info=ref_info,
            override_record=ov_record,
            provider_lookup_result=None,  # Provider cross-check done separately
            name_search_result=name_search_result,
        )

        resolution_entry = {
            "resolved_fund_code": resolved_code,
            "raw_reference": fund_key,
            "raw_fund_code": raw_fund_code,
            "raw_fund_name": raw_fund_name,
            "normalized_name": normalize_fund_name(raw_fund_name) if raw_fund_name else None,
            "fund_name": raw_fund_name,
            "resolution_source": resolution_source,
            "resolution_status": resolution_status,
            "identity_verification_status": identity_verification_status,
            "confidence": confidence,
            "candidates": candidates,
            "audit_trail": audit_steps,
        }

        # M7.11: Attach name search candidates if discovered
        if name_search_candidates_data:
            resolution_entry["name_search_candidates"] = name_search_candidates_data

        resolutions.append(resolution_entry)

    summary = {
        "total_funds": len(resolutions),
        "valid_fund_codes_count": sum(1 for r in resolutions if r["resolved_fund_code"] is not None),
        "name_only_count": sum(1 for r in resolutions if r["resolution_status"] == "name_only"),
        "identity_mismatch_count": sum(1 for r in resolutions if r["identity_verification_status"] == "code_name_mismatch"),
        "code_unverified_count": sum(1 for r in resolutions if r["identity_verification_status"] == "code_unverified"),
        "high_confidence": sum(1 for r in resolutions if r["confidence"] == "high"),
        "medium_confidence": sum(1 for r in resolutions if r["confidence"] == "medium"),
        "low_confidence_count": sum(1 for r in resolutions if r["confidence"] == "low"),
        "unresolved_count": sum(1 for r in resolutions if r["resolution_source"] == "none"),
        "manual_overrides_used": bool(ov_lookup or overrides),
        "manual_override_matches_count": sum(1 for r in resolutions if r["resolution_source"] == "manual_override"),
        "name_search_enabled": enable_name_search,
        "name_search_auto_verified_count": sum(1 for r in resolutions if r["resolution_source"] == "name_search_auto_verified"),
        "name_search_candidate_unverified_count": sum(1 for r in resolutions if r["identity_verification_status"] == "name_search_candidate_unverified"),
        "resolution_status_counts": {
            "valid_code": sum(1 for r in resolutions if r["resolution_status"] == "valid_code"),
            "manual_override": sum(1 for r in resolutions if r["resolution_status"] == "manual_override"),
            "name_only": sum(1 for r in resolutions if r["resolution_status"] == "name_only"),
            "invalid_code": sum(1 for r in resolutions if r["resolution_status"] == "invalid_code"),
            "unresolved": sum(1 for r in resolutions if r["resolution_status"] == "unresolved"),
        },
        "identity_verification_status_counts": {
            "verified": sum(1 for r in resolutions if r["identity_verification_status"] == "verified"),
            "provider_verified": sum(1 for r in resolutions if r["identity_verification_status"] == "provider_verified"),
            "user_verified_override": sum(1 for r in resolutions if r["identity_verification_status"] == "user_verified_override"),
            "manual_override_unverified": sum(1 for r in resolutions if r["identity_verification_status"] == "manual_override_unverified"),
            "provider_lookup_failed": sum(1 for r in resolutions if r["identity_verification_status"] == "provider_lookup_failed"),
            "code_name_mismatch": sum(1 for r in resolutions if r["identity_verification_status"] == "code_name_mismatch"),
            "code_unverified": sum(1 for r in resolutions if r["identity_verification_status"] == "code_unverified"),
            "name_only": sum(1 for r in resolutions if r["identity_verification_status"] == "name_only"),
            "invalid_code": sum(1 for r in resolutions if r["identity_verification_status"] == "invalid_code"),
            "name_search_candidate_unverified": sum(1 for r in resolutions if r["identity_verification_status"] == "name_search_candidate_unverified"),
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
    parser.add_argument("--enable-name-search", action="store_true", default=False,
                        help="Enable M7.11 name-based fund identity candidate discovery")
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
        name_search_provider=None,  # CLI does not inject provider; use programmatically
        enable_name_search=args.enable_name_search,
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
