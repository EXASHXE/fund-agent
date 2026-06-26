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

    # Determine recommended questions based on reason codes
    questions: list[str] = []
    if "name_only_funds" in reason_codes or "no_valid_fund_codes" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[0])
    if "partial_nav_coverage" in reason_codes or "nav_missing" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[1])
    if "manual_review_transactions" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[2])
    if "fallback_holdings_used" in reason_codes or "unavailable" in overall_status:
        questions.append(_RECOMMENDED_QUESTIONS[3])
    if "cashflow_only" in reason_codes or "estimated_only" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[5])
    if "stale_nav" in reason_codes or "qdii_nav_lag" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[4])
    if "identity_mismatch" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[6])
    if "identity_unverified" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[8])
    if "partial_valuation" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[9])
    if "redemption_fee_unknown" in reason_codes:
        questions.append(_RECOMMENDED_QUESTIONS[7])
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
