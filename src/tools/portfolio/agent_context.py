"""Agent-facing analysis context builder.

Generates structured context (JSON + Markdown) that external agents can consume
to understand what data is available, what they can safely analyze, and what
they should NOT infer. No private data in output — only status labels, counts,
and relative artifact paths.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "fund_agent_context.v1"

# ── Allowed reason codes (stable enumeration) ─────────────────────────
REASON_CODES = frozenset({
    "no_valid_fund_codes",
    "name_only_funds",
    "nav_missing",
    "partial_nav_coverage",
    "manual_review_transactions",
    "stale_nav",
    "qdii_nav_lag",
    "fallback_holdings_used",
    "cashflow_only",
    "estimated_only",
    "identity_mismatch",
    "identity_unverified",
    "partial_valuation",
    "redemption_fee_unknown",
    "insufficient_trade_date_nav_coverage",
    "no_holdings_snapshot",
    "reconciliation_gap",
    "transaction_derived_valuation",
    "reconstruction_partial",
    "dividend_unmodeled",
    "unmatched_refund",
    "conversion_unverified",
    "unknown_amount_semantics",
    "missing_fee",
    "name_search_candidates_unverified",
    "provider_name_search_network_error",
    "provider_name_search_unavailable",
    "identity_candidate_cache_missing",
    "identity_candidate_cache_used",
    "identity_candidates_generated_from_cache",
    "name_search_provider_chain_failed",
})

# ── Allowed safety constraints (stable enumeration) ────────────────────
SAFETY_CONSTRAINTS = frozenset({
    "not_formal_decision",
    "no_auto_trading",
    "no_broker_or_order_execution",
    "estimated_values_are_not_confirmed",
    "partial_not_complete_market_value",
})

# ── Allowed safe-to-analyze items ─────────────────────────────────────
SAFE_TO_ANALYZE_ITEMS = frozenset({
    "cashflow_trend",
    "estimated_valuation_with_partial_coverage",
    "holdings_fallback",
    "transaction_quality",
    "nav_coverage_quality",
    "holdings_snapshot_valuation",
    "platform_reported_profit_and_cost",
    "transaction_derived_current_value",
    "reconstruction_quality",
    "name_search_candidates",
    "identity_candidate_cache",
})

# ── Allowed unsafe-to-infer items ─────────────────────────────────────
UNSAFE_TO_INFER_ITEMS = frozenset({
    "complete_market_value_if_coverage_partial",
    "confirmed_p_and_l_if_valuation_estimated",
    "trading_decision",
    "broker_or_order_execution",
    "valuation_if_identity_mismatch",
    "valuation_if_identity_unverified",
    "complete_market_value_if_partial_valuation",
    "market_value_without_holdings_snapshot",
    "reconcile_snapshot_discrepancy_automatically",
    "nav_trend_from_unverified_identity",
    "fund_code_from_manual_override_without_verification",
    "p_and_l_from_avg_cost_nav_comparison",
    "complete_identity_from_candidate_code",
    "platform_reported_value_from_reconstruction",
    "confirmed_profit_without_fee_coverage",
    "confirmed_identity_from_name_search_unverified",
})

# ── Safe-to-analyze scope ─────────────────────────────────────────────
_SAFE_TO_ANALYZE = sorted(SAFE_TO_ANALYZE_ITEMS)

# ── Unsafe-to-infer scope ─────────────────────────────────────────────
_UNSAFE_TO_INFER = sorted(UNSAFE_TO_INFER_ITEMS)

# ── Safety constraints ────────────────────────────────────────────────
_SAFETY_CONSTRAINTS = sorted(SAFETY_CONSTRAINTS)

# ── Recommended agent questions (data quality, not trading advice) ────
_RECOMMENDED_QUESTIONS = [
    "Should fund_identity_overrides be provided for name-only funds?",
    "Should trade-date NAV be provided for partial coverage?",
    "Should conversion/refund transactions be confirmed?",
    "Should portfolio_input.holdings be provided as fallback?",
    "Should the host query live NAV or news data?",
    "Should explicit units be provided for cashflow-only transactions?",
    "Should fund_identity_overrides be verified for code/name mismatched funds?",
    "Should fee_overrides be provided for funds with unknown redemption fees?",
    "Should fund_identity_overrides be verified (verified_by_user or provider cross-check) for unverified manual overrides?",
    "Should trade-date NAV or explicit units be provided to complete valuation coverage?",
    "Should a current holdings snapshot be provided for authoritative valuation?",
    "Should reconciliation gaps between snapshot and transaction history be manually verified?",
    "Should name search candidates be reviewed and verified for funds without fund_code?",
    "Should a local identity candidate cache be populated for offline name search fallback?",
    "Should the identity_candidate_cache_minimal.private.csv template be filled in (fund_code + fund_name only) for offline identity resolution?",
]

# M7.6: Identity-specific recommended questions (replace generic ones when identity is blocked)
_IDENTITY_BLOCKED_QUESTIONS = [
    "请从支付宝当前持仓页核对基金代码和基金名称是否一致。",
    "请提供 current_holdings_snapshot.private.csv，其中包含 fund_code/fund_name/current_value 或 shares。",
    "不要仅为了通过门控添加 verified_by_user:true。",
]


def build_agent_context(
    summary: Mapping[str, Any],
    *,
    run_id: str = "",
    artifact_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build agent-facing context from E2E summary and health report.

    Args:
        summary: E2E summary dict (from e2e_summary.json) or any mapping
            containing personal_health_report data.
        run_id: Run identifier.
        artifact_paths: Relative artifact paths within the run directory.

    Returns:
        Structured agent context dict conforming to fund_agent_context.v1.
    """
    from src.tools.portfolio.evidence_visibility import (
        BLOCKED_IDENTITY_STATUSES,
        compute_blocked_evidence_summary,
    )

    health = _as_dict(summary.get("personal_health_report"))
    overall_status = str(health.get("overall_status", "unavailable"))
    confidence_level = str(health.get("confidence_level", "unavailable"))
    reason_codes = list(health.get("reason_codes", []))

    # Determine safe-to-analyze based on data availability
    safe = list(_SAFE_TO_ANALYZE)
    if overall_status == "unavailable":
        safe = []

    # Determine unsafe-to-infer based on coverage
    unsafe = list(_UNSAFE_TO_INFER)
    nav_coverage = _as_dict(health.get("nav_coverage"))
    nav_partial = int(nav_coverage.get("partial", 0))
    nav_none = int(nav_coverage.get("none", 0))
    if nav_partial == 0 and nav_none == 0:
        # Full coverage — can infer market value
        unsafe = [u for u in unsafe if u != "complete_market_value_if_coverage_partial"]

    # Holdings snapshot availability affects unsafe-to-infer scope
    holdings_snapshot_loaded = bool(
        _as_dict(summary.get("holdings_snapshot")).get("loaded", False)
    )
    if holdings_snapshot_loaded:
        # Snapshot available — can reference platform-reported values
        unsafe = [u for u in unsafe if u != "market_value_without_holdings_snapshot"]
        safe.append("holdings_snapshot_valuation")
        safe.append("platform_reported_profit_and_cost")
    else:
        # No snapshot — market value inference is unsafe
        if "market_value_without_holdings_snapshot" not in unsafe:
            unsafe.append("market_value_without_holdings_snapshot")

    # M7.6: Compute blocked evidence summary from positions
    positions = _extract_positions(summary)
    blocked_summary = compute_blocked_evidence_summary(positions)

    # If identity is blocked, add identity-specific unsafe items
    has_identity_blocked = blocked_summary["nav_trend_blocked"]
    if has_identity_blocked:
        for item in ("nav_trend_from_unverified_identity", "fund_code_from_manual_override_without_verification",
                     "p_and_l_from_avg_cost_nav_comparison", "complete_identity_from_candidate_code"):
            if item not in unsafe:
                unsafe.append(item)

    # Determine recommended questions based on reason codes
    # M7.14: Identity discovery blockers come FIRST
    questions: list[str] = []

    # Identity discovery blockers — highest priority
    if "name_search_provider_chain_failed" in reason_codes or "identity_candidate_cache_missing" in reason_codes:
        # Minimal cache template question (most actionable)
        questions.append(_RECOMMENDED_QUESTIONS[14])
        questions.append(_RECOMMENDED_QUESTIONS[13])
    if "name_only_funds" in reason_codes or "no_valid_fund_codes" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[0])
    if "name_search_candidates_unverified" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[12])

    # Identity verification
    if "identity_mismatch" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[6])
    if "identity_unverified" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[8])
        for q in _IDENTITY_BLOCKED_QUESTIONS:
            if q not in questions:
                questions.append(q)

    # NAV / valuation — only after identity is addressed
    if "partial_nav_coverage" in reason_codes or "nav_missing" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[1])
    if "partial_valuation" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[9])
    if "redemption_fee_unknown" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[7])

    # Other
    if "manual_review_transactions" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[2])
    if "fallback_holdings_used" in reason_codes or "unavailable" in overall_status:
        questions.append(_RECOMMENDED_QUESTIONS[3])
    if "cashflow_only" in reason_codes or "estimated_only" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[5])
    if "stale_nav" in reason_codes or "qdii_nav_lag" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[4])
    if "no_holdings_snapshot" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[10])
    if "reconciliation_gap" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[11])
    # Always include if no specific questions matched
    if not questions:
        questions.append(_RECOMMENDED_QUESTIONS[4])

    # Default artifact paths (relative). Legacy summaries without explicit
    # output metadata keep the historical report entry; modern summaries can
    # explicitly suppress it with outputs.report/output_report = null.
    default_artifacts = {
        "e2e_summary": "e2e_summary.json",
        "personal_health_report": "personal_health_report.json",
    }
    if _summary_report_available(summary):
        default_artifacts["report"] = "report.md"
    if artifact_paths:
        default_artifacts.update(artifact_paths)
        if "report" not in artifact_paths and _summary_explicitly_has_no_report(summary):
            default_artifacts.pop("report", None)

    # Check if reconstructed portfolio is available
    pipeline_steps = _as_dict(summary.get("pipeline_steps"))
    if pipeline_steps.get("reconstruction_status") == "reconstructed_from_ledger":
        default_artifacts["portfolio"] = "portfolio/confirmed_portfolio.private.json"

    # M7.6: Add fixit identity candidates path if generated
    if has_identity_blocked:
        default_artifacts["identity_candidates"] = "fixit/identity_candidates.private.csv"

    # M7.9: Reconstruction summary
    reconstruction_summary = _compute_reconstruction_summary(positions)

    # M7.9: Adjust safe/unsafe based on reconstruction quality
    if reconstruction_summary.get("transaction_derived_full_count", 0) > 0:
        safe.append("transaction_derived_current_value")
        safe.append("reconstruction_quality")
        # If we have transaction-derived valuation, market value without snapshot is no longer unsafe
        # BUT only for transaction_derived_full, not partial
        if "market_value_without_holdings_snapshot" in unsafe:
            # Keep it unsafe but add nuance — only if all positions are transaction_derived_full
            if reconstruction_summary.get("transaction_derived_partial_count", 0) == 0:
                unsafe = [u for u in unsafe if u != "market_value_without_holdings_snapshot"]

    # M7.12: Name search diagnostics from e2e_summary
    name_search_diag: dict[str, Any] = {}
    ns_provider = _as_dict(summary.get("name_search_provider_diagnostics"))
    if ns_provider:
        name_search_diag = {
            "name_search_provider_type": ns_provider.get("name_search_provider_type", ""),
            "name_search_provider_status": ns_provider.get("name_search_provider_status", ""),
            "name_search_provider_search_count": ns_provider.get("name_search_provider_search_count", 0),
            "name_search_provider_result_count": ns_provider.get("name_search_provider_result_count", 0),
        }
        # M7.13: Provider chain diagnostics
        if ns_provider.get("provider_chain_enabled"):
            name_search_diag["provider_chain_enabled"] = True
            name_search_diag["providers_attempted"] = ns_provider.get("providers_attempted", [])
            name_search_diag["providers_succeeded"] = ns_provider.get("providers_succeeded", [])
            name_search_diag["providers_failed"] = ns_provider.get("providers_failed", [])
            name_search_diag["fallback_used"] = ns_provider.get("fallback_used", False)
        # M7.16: Exact lookup diagnostics
        if ns_provider.get("fund_universe_size") is not None:
            name_search_diag["fund_universe_size"] = ns_provider.get("fund_universe_size", 0)
            name_search_diag["exact_full_name_match_count"] = ns_provider.get("exact_full_name_match_count", 0)
            name_search_diag["exact_without_punctuation_match_count"] = ns_provider.get("exact_without_punctuation_match_count", 0)
            name_search_diag["core_share_class_match_count"] = ns_provider.get("core_share_class_match_count", 0)
            name_search_diag["fuzzy_fallback_count"] = ns_provider.get("fuzzy_fallback_count", 0)
            name_search_diag["search_strategy_used"] = ns_provider.get("search_strategy_used", "")
    # Also extract from identity resolution summary
    id_summary = _as_dict(summary.get("identity_resolution"))
    if id_summary:
        name_search_diag["name_search_enabled"] = id_summary.get("name_search_enabled", False)
        name_search_diag["name_search_auto_verified_count"] = id_summary.get("name_search_auto_verified_count", 0)
        name_search_diag["name_search_candidate_unverified_count"] = id_summary.get("name_search_candidate_unverified_count", 0)
        # M7.16: Exact lookup summary from identity resolution
        name_search_diag["exact_lookup_failed_count"] = id_summary.get("exact_lookup_failed_count", 0)
        name_search_diag["fuzzy_candidate_count"] = id_summary.get("fuzzy_candidate_count", 0)
        name_search_diag["hard_rejected_candidate_count"] = id_summary.get("hard_rejected_candidate_count", 0)
    # M7.13: Local cache diagnostics
    local_cache_diag = _as_dict(summary.get("local_cache_diagnostics"))
    if local_cache_diag:
        name_search_diag["local_cache_present"] = local_cache_diag.get(
            "name_search_provider_status", "") != "cache_missing"
        name_search_diag["local_cache_candidate_count"] = local_cache_diag.get(
            "name_search_provider_entry_count", 0)
        name_search_diag["network_provider_status"] = (
            "network_error" if any(
                "akshare" in p.lower() or "network" in p.lower()
                for p in ns_provider.get("providers_failed", [])
            ) else "available"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": overall_status,
        "confidence_level": confidence_level,
        "reason_codes": reason_codes,
        "safe_to_analyze": safe,
        "unsafe_to_infer": unsafe,
        "recommended_agent_questions": questions,
        "artifact_paths": default_artifacts,
        "safety_constraints": list(_SAFETY_CONSTRAINTS),
        "blocked_evidence_summary": blocked_summary,
        "reconstruction_summary": reconstruction_summary,
        "name_search_diagnostics": name_search_diag,
    }


def render_agent_context_markdown(context: Mapping[str, Any]) -> str:
    """Render agent context as Markdown for agent consumption.

    Args:
        context: Agent context dict (output of build_agent_context).

    Returns:
        Markdown string with all sections.
    """
    lines: list[str] = []

    lines.append("# Fund Agent Analysis Context")
    lines.append("")

    # ── Data readiness ────────────────────────────────────────────────
    lines.append("## Data Readiness")
    lines.append("")
    lines.append(f"- **Overall status:** {context.get('overall_status', 'unavailable')}")
    lines.append(f"- **Confidence level:** {context.get('confidence_level', 'unavailable')}")
    reason_codes = context.get("reason_codes", [])
    if reason_codes:
        lines.append(f"- **Reason codes:** {', '.join(reason_codes)}")
    else:
        lines.append("- **Reason codes:** (none)")
    lines.append("")

    # ── Blocked evidence summary (M7.6) ──────────────────────────────
    blocked = _as_dict(context.get("blocked_evidence_summary"))
    if blocked and blocked.get("nav_trend_blocked"):
        lines.append("## Blocked Evidence Summary")
        lines.append("")
        lines.append(f"- **Candidate code count:** {blocked.get('candidate_code_count', 0)}")
        lines.append(f"- **Estimated units blocked:** {blocked.get('estimated_units_blocked_count', 0)}")
        lines.append(f"- **Latest NAV blocked:** {blocked.get('latest_nav_blocked_count', 0)}")
        lines.append(f"- **NAV trend blocked:** {blocked.get('nav_trend_blocked', False)}")
        reasons = blocked.get("reasons", [])
        if reasons:
            lines.append(f"- **Reasons:** {', '.join(reasons)}")
        lines.append("")
        lines.append("> **M7.6 Firewall:** When identity is unverified, candidate codes, NAV trend,")
        lines.append("> P&L, and valuation conclusions are blocked from agent analysis.")
        lines.append("> Do NOT bypass this firewall. Verify fund codes first.")
        lines.append("")

    # ── Safe-to-analyze scope ─────────────────────────────────────────
    lines.append("## Safe-to-Analyze Scope")
    lines.append("")
    lines.append("The agent can safely analyze:")
    for item in context.get("safe_to_analyze", []):
        lines.append(f"- {item}")
    lines.append("")

    # ── Unsafe-to-infer scope ─────────────────────────────────────────
    lines.append("## Unsafe-to-Infer Scope")
    lines.append("")
    lines.append("The agent should NOT infer:")
    for item in context.get("unsafe_to_infer", []):
        lines.append(f"- {item}")
    lines.append("")

    # ── Evidence map ──────────────────────────────────────────────────
    lines.append("## Evidence Map")
    lines.append("")
    lines.append("Local artifacts (relative paths within run directory):")
    artifacts = context.get("artifact_paths", {})
    for name, path in artifacts.items():
        lines.append(f"- `{path}` ({name})")
    lines.append("")

    # ── Suggested agent follow-up questions ───────────────────────────
    lines.append("## Suggested Agent Follow-up Questions")
    lines.append("")
    lines.append("These are data-quality questions, not trading advice:")
    for q in context.get("recommended_agent_questions", []):
        lines.append(f"- {q}")
    lines.append("")

    # ── Safety constraints ────────────────────────────────────────────
    lines.append("## Safety Constraints")
    lines.append("")
    for c in context.get("safety_constraints", []):
        lines.append(f"- {c}")
    lines.append("")

    # ── M7.16: Exact lookup diagnostics ──────────────────────────────
    ns_diag = _as_dict(context.get("name_search_diagnostics"))
    if ns_diag and ns_diag.get("fund_universe_size") is not None:
        lines.append("## Exact Lookup Diagnostics")
        lines.append("")
        lines.append(f"- **Fund universe size:** {ns_diag.get('fund_universe_size', 0)}")
        lines.append(f"- **Exact full name match count:** {ns_diag.get('exact_full_name_match_count', 0)}")
        lines.append(f"- **Exact without punctuation match count:** {ns_diag.get('exact_without_punctuation_match_count', 0)}")
        lines.append(f"- **Core share class match count:** {ns_diag.get('core_share_class_match_count', 0)}")
        lines.append(f"- **Fuzzy fallback count:** {ns_diag.get('fuzzy_fallback_count', 0)}")
        lines.append(f"- **Exact lookup failed count:** {ns_diag.get('exact_lookup_failed_count', 0)}")
        lines.append(f"- **Fuzzy candidate count:** {ns_diag.get('fuzzy_candidate_count', 0)}")
        lines.append(f"- **Hard rejected candidate count:** {ns_diag.get('hard_rejected_candidate_count', 0)}")
        lines.append(f"- **Last search strategy:** {ns_diag.get('search_strategy_used', '')}")
        lines.append("")
        # M7.16: Non-exact candidate codes are NOT displayed in public output
        fuzzy_count = ns_diag.get('fuzzy_candidate_count', 0)
        exact_failed = ns_diag.get('exact_lookup_failed_count', 0)
        if fuzzy_count > 0 or exact_failed > 0:
            lines.append("> **M7.16:** Non-exact candidate codes are not displayed in public output.")
            lines.append("> Please check fixit/identity_candidates.private.csv for candidate details.")
            lines.append("")

    return "\n".join(lines)


# ── Internal helpers ──────────────────────────────────────────────────


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _summary_explicitly_has_no_report(summary: Mapping[str, Any]) -> bool:
    outputs = _as_dict(summary.get("outputs"))
    if "report" in outputs:
        return outputs.get("report") in (None, "")
    if "output_report" in summary:
        return summary.get("output_report") in (None, "")
    return False


def _summary_report_available(summary: Mapping[str, Any]) -> bool:
    outputs = _as_dict(summary.get("outputs"))
    if "report" in outputs:
        return bool(outputs.get("report"))
    if "output_report" in summary:
        return bool(summary.get("output_report"))
    return True


def _extract_positions(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract position list from E2E summary for blocked evidence computation.

    Looks in confirmed_portfolio.positions or position_summary.
    """
    positions: list[dict[str, Any]] = []

    # Try confirmed_portfolio first
    cp = _as_dict(summary.get("confirmed_portfolio"))
    cp_positions = _as_list(cp.get("positions"))
    if cp_positions:
        for pos in cp_positions:
            if isinstance(pos, dict):
                positions.append(pos)
        return positions

    # Try position_summary (dict keyed by fund_code)
    ps = _as_dict(summary.get("position_summary"))
    if ps:
        for _code, pos in ps.items():
            if isinstance(pos, dict):
                positions.append(pos)
        return positions

    # Try from portfolio_summary embedded positions
    portfolio = _as_dict(summary.get("portfolio_summary"))
    portfolio_positions = _as_list(portfolio.get("positions"))
    if portfolio_positions:
        for pos in portfolio_positions:
            if isinstance(pos, dict):
                positions.append(pos)

    return positions


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _compute_reconstruction_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute reconstruction summary from position list (M7.9)."""
    if not positions:
        return {}

    holdings_sources = [p.get("holdings_source", "unavailable") for p in positions]
    recon_qualities = [p.get("reconstruction_quality", "") for p in positions]

    return {
        "transaction_derived_full_count": sum(1 for h in holdings_sources if h == "transaction_derived_full"),
        "transaction_derived_partial_count": sum(1 for h in holdings_sources if h == "transaction_derived_partial"),
        "platform_reported_snapshot_count": sum(1 for h in holdings_sources if h == "platform_reported_snapshot"),
        "cashflow_only_count": sum(1 for h in holdings_sources if h == "cashflow_only"),
        "unavailable_count": sum(1 for h in holdings_sources if h == "unavailable"),
        "reconstruction_quality_by_position": {
            "confirmed": sum(1 for q in recon_qualities if q == "confirmed"),
            "estimated_high": sum(1 for q in recon_qualities if q == "estimated_high"),
            "estimated_medium": sum(1 for q in recon_qualities if q == "estimated_medium"),
            "estimated_low": sum(1 for q in recon_qualities if q == "estimated_low"),
            "partial": sum(1 for q in recon_qualities if q == "partial"),
            "blocked": sum(1 for q in recon_qualities if q == "blocked"),
        },
    }
