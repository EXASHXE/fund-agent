"""M7.18: Expected Identity Oracle Diagnostics.

Compares agent auto-identification results against a private expected map
to produce desensitized statistics and a private debug CSV.

Key invariants:
- Oracle data is NEVER used for runtime resolution.
- Oracle codes are NEVER written to resolved_fund_code.
- Oracle codes are NEVER used as provider_verified.
- Oracle does NOT unlock transaction-derived valuation.
- If wrong_code > 0, valuation MUST be blocked.
- Public summary contains ONLY desensitized counts — no fund names, codes, amounts.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Oracle match results ────────────────────────────────────────────────

ORACLE_EXACT_CORRECT = "exact_correct"
ORACLE_EXACT_MISSED = "exact_missed"
ORACLE_WRONG_CODE = "wrong_code"
ORACLE_UNRESOLVED = "unresolved"
ORACLE_NAME_VARIANT = "name_variant"
ORACLE_PROVIDER_UNIVERSE_MISSING = "provider_universe_missing"


@dataclass
class OracleDiffEntry:
    """Single fund's oracle comparison result."""

    raw_fund_name: str
    expected_fund_code: str
    expected_provider_name: str
    agent_resolved_code: str | None
    agent_resolution_source: str
    agent_identity_status: str
    agent_match_reason: str
    oracle_match_result: str
    likely_root_cause: str
    recommended_fix: str


@dataclass
class OraclePublicSummary:
    """Desensitized oracle comparison summary — no fund names or codes."""

    oracle_total: int = 0
    oracle_exact_correct_count: int = 0
    oracle_exact_missed_count: int = 0
    oracle_wrong_code_count: int = 0
    oracle_unresolved_count: int = 0
    oracle_name_variant_count: int = 0
    oracle_provider_universe_missing_count: int = 0
    non_exact_auto_verified_count: int = 0
    fuzzy_auto_verified_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_total": self.oracle_total,
            "oracle_exact_correct_count": self.oracle_exact_correct_count,
            "oracle_exact_missed_count": self.oracle_exact_missed_count,
            "oracle_wrong_code_count": self.oracle_wrong_code_count,
            "oracle_unresolved_count": self.oracle_unresolved_count,
            "oracle_name_variant_count": self.oracle_name_variant_count,
            "oracle_provider_universe_missing_count": self.oracle_provider_universe_missing_count,
            "non_exact_auto_verified_count": self.non_exact_auto_verified_count,
            "fuzzy_auto_verified_count": self.fuzzy_auto_verified_count,
        }


def load_expected_identity_map(csv_path: Path) -> list[dict[str, str]]:
    """Load expected fund identity map from private CSV.

    Expected CSV columns: raw_fund_name, expected_fund_code, expected_provider_name
    """
    entries = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row.get("raw_fund_name", "").strip()
            expected_code = row.get("expected_fund_code", "").strip()
            expected_provider_name = row.get("expected_provider_name", "").strip()
            if raw_name and expected_code:
                entries.append({
                    "raw_fund_name": raw_name,
                    "expected_fund_code": expected_code,
                    "expected_provider_name": expected_provider_name,
                })
    return entries


def _classify_oracle_match(
    expected_code: str,
    agent_resolved_code: str | None,
    agent_identity_status: str,
    agent_match_reason: str,
    expected_provider_name: str,
    raw_fund_name: str,
) -> tuple[str, str, str]:
    """Classify the oracle match result and determine root cause + fix.

    Returns (oracle_match_result, likely_root_cause, recommended_fix).
    """
    # Agent has no resolved code
    if not agent_resolved_code:
        if agent_identity_status == "name_search_candidate_unverified":
            # Check if it's a name variant
            if _is_likely_name_variant(raw_fund_name, expected_provider_name):
                return (
                    ORACLE_NAME_VARIANT,
                    "name_variant: transaction name differs from provider universe name",
                    "add_trusted_alias: add expected_provider_name as trusted alias for exact match",
                )
            return (
                ORACLE_EXACT_MISSED,
                "no_exact_universe_match: provider name search could not find exact match",
                "check_provider_universe: verify fund exists in akshare fund universe",
            )
        # name_only or code_unverified
        if _is_likely_name_variant(raw_fund_name, expected_provider_name):
            return (
                ORACLE_NAME_VARIANT,
                "name_variant: transaction name differs from provider universe name",
                "add_trusted_alias: add expected_provider_name as trusted alias for exact match",
            )
        return (
            ORACLE_UNRESOLVED,
            "unresolved: no candidate found by agent",
            "manual_verify: manually verify fund code and add to overrides",
        )

    # Agent resolved a code — check if it matches expected
    if agent_resolved_code == expected_code:
        return (ORACLE_EXACT_CORRECT, "none", "none")
    else:
        return (
            ORACLE_WRONG_CODE,
            f"wrong_code: agent resolved {agent_resolved_code} but expected {expected_code}",
            "block_valuation: wrong_code > 0 blocks transaction-derived valuation",
        )


def _is_likely_name_variant(raw_name: str, expected_provider_name: str) -> bool:
    """Heuristic: check if raw_name is likely a name variant of expected_provider_name.

    Common variant patterns:
    - 发起式 prefix
    - 中短债纯债 vs 短债债券
    - 低波 vs 低波动
    - QDII A/C share class differences
    - ETF联接 abbreviation differences
    """
    if not raw_name or not expected_provider_name:
        return False

    # Strip share class suffix for comparison
    def strip_share_class(name: str) -> str:
        for suffix in ("A", "C"):
            if name.endswith(suffix) and len(name) > 1:
                return name[:-1]
        return name

    raw_core = strip_share_class(raw_name)
    exp_core = strip_share_class(expected_provider_name)

    # If cores are identical, not a variant (should have matched exactly)
    if raw_core == exp_core:
        return False

    # Check common variant patterns
    variant_pairs = [
        ("发起式", ""),
        ("中短债纯债", "短债债券"),
        ("短债债券", "中短债纯债"),
        ("低波", "低波动"),
        ("低波动", "低波"),
    ]
    for a, b in variant_pairs:
        modified_raw = raw_core.replace(a, b) if b else raw_core.replace(a, "")
        if modified_raw == exp_core:
            return True

    # Check if one is a substring of the other (after removing common prefixes)
    if len(raw_core) > 2 and len(exp_core) > 2:
        # Remove brand prefix (first 2-4 chars) and compare remainder
        if raw_core[-len(exp_core):] == exp_core or exp_core[-len(raw_core):] == raw_core:
            return True

    return False


def compute_oracle_diagnostics(
    expected_entries: list[dict[str, str]],
    resolutions: list[dict[str, Any]],
) -> tuple[list[OracleDiffEntry], OraclePublicSummary]:
    """Compare agent resolutions against expected identity map.

    Args:
        expected_entries: List of dicts with raw_fund_name, expected_fund_code, expected_provider_name
        resolutions: List of identity resolution dicts from resolve_fund_identities

    Returns:
        Tuple of (diff_entries, public_summary)
    """
    # Build lookup from raw_fund_name → resolution
    resolution_by_name: dict[str, dict[str, Any]] = {}
    for res in resolutions:
        name = res.get("raw_fund_name") or res.get("fund_name", "")
        if name:
            resolution_by_name[name] = res

    diff_entries: list[OracleDiffEntry] = []
    summary = OraclePublicSummary()

    # Track non-exact auto-verified and fuzzy auto-verified from resolutions
    for res in resolutions:
        source = res.get("resolution_source", "")
        ivs = res.get("identity_verification_status", "")
        candidates = res.get("name_search_candidates", [])

        if source == "name_search_auto_verified":
            top_reasons = candidates[0].get("match_reasons", []) if candidates else []
            from src.tools.portfolio.fund_identity_candidate_discovery import _EXACT_MATCH_REASONS
            has_exact = any(r in _EXACT_MATCH_REASONS for r in top_reasons)
            if not has_exact:
                summary.non_exact_auto_verified_count += 1

            top_source = candidates[0].get("source", "") if candidates else ""
            if "fuzzy" in top_source.lower() or "fuzzy_fallback" in top_reasons:
                summary.fuzzy_auto_verified_count += 1

    for entry in expected_entries:
        raw_name = entry["raw_fund_name"]
        expected_code = entry["expected_fund_code"]
        expected_provider_name = entry["expected_provider_name"]

        # Find matching resolution
        res = resolution_by_name.get(raw_name)
        if res is None:
            # No resolution found for this expected entry
            diff = OracleDiffEntry(
                raw_fund_name=raw_name,
                expected_fund_code=expected_code,
                expected_provider_name=expected_provider_name,
                agent_resolved_code=None,
                agent_resolution_source="none",
                agent_identity_status="unresolved",
                agent_match_reason="",
                oracle_match_result=ORACLE_UNRESOLVED,
                likely_root_cause="unresolved: no resolution found for this fund name",
                recommended_fix="check_raw_name: verify raw_fund_name matches transaction ledger",
            )
            diff_entries.append(diff)
            summary.oracle_total += 1
            summary.oracle_unresolved_count += 1
            continue

        agent_code = res.get("resolved_fund_code")
        agent_source = res.get("resolution_source", "")
        agent_ivs = res.get("identity_verification_status", "")

        # Get top match reason
        candidates = res.get("name_search_candidates", [])
        if candidates:
            top_reasons = candidates[0].get("match_reasons", [])
            agent_match_reason = top_reasons[0] if top_reasons else ""
        else:
            agent_match_reason = ""

        match_result, root_cause, fix = _classify_oracle_match(
            expected_code=expected_code,
            agent_resolved_code=agent_code,
            agent_identity_status=agent_ivs,
            agent_match_reason=agent_match_reason,
            expected_provider_name=expected_provider_name,
            raw_fund_name=raw_name,
        )

        diff = OracleDiffEntry(
            raw_fund_name=raw_name,
            expected_fund_code=expected_code,
            expected_provider_name=expected_provider_name,
            agent_resolved_code=agent_code,
            agent_resolution_source=agent_source,
            agent_identity_status=agent_ivs,
            agent_match_reason=agent_match_reason,
            oracle_match_result=match_result,
            likely_root_cause=root_cause,
            recommended_fix=fix,
        )
        diff_entries.append(diff)
        summary.oracle_total += 1

        if match_result == ORACLE_EXACT_CORRECT:
            summary.oracle_exact_correct_count += 1
        elif match_result == ORACLE_EXACT_MISSED:
            summary.oracle_exact_missed_count += 1
        elif match_result == ORACLE_WRONG_CODE:
            summary.oracle_wrong_code_count += 1
        elif match_result == ORACLE_UNRESOLVED:
            summary.oracle_unresolved_count += 1
        elif match_result == ORACLE_NAME_VARIANT:
            summary.oracle_name_variant_count += 1
        elif match_result == ORACLE_PROVIDER_UNIVERSE_MISSING:
            summary.oracle_provider_universe_missing_count += 1

    return diff_entries, summary


def write_oracle_diff_csv(
    diff_entries: list[OracleDiffEntry],
    output_path: Path,
) -> None:
    """Write private oracle diff CSV with all details including codes and names."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "raw_fund_name",
        "expected_fund_code",
        "expected_provider_name",
        "agent_resolved_code",
        "agent_resolution_source",
        "agent_identity_status",
        "agent_match_reason",
        "oracle_match_result",
        "likely_root_cause",
        "recommended_fix",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in diff_entries:
            writer.writerow({
                "raw_fund_name": entry.raw_fund_name,
                "expected_fund_code": entry.expected_fund_code,
                "expected_provider_name": entry.expected_provider_name,
                "agent_resolved_code": entry.agent_resolved_code or "",
                "agent_resolution_source": entry.agent_resolution_source,
                "agent_identity_status": entry.agent_identity_status,
                "agent_match_reason": entry.agent_match_reason,
                "oracle_match_result": entry.oracle_match_result,
                "likely_root_cause": entry.likely_root_cause,
                "recommended_fix": entry.recommended_fix,
            })


def oracle_wrong_code_blocks_valuation(summary: OraclePublicSummary) -> bool:
    """If wrong_code > 0, block transaction-derived valuation."""
    return summary.oracle_wrong_code_count > 0
