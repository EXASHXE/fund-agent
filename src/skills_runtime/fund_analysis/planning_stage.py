"""Analysis plan and evidence gap diagnostics for FundAnalysisSkill.

Deterministic, local-only planning stage. Produces two artifacts:
- analysis_plan: tells the external host/agent what data is available,
  what is missing, which skills to call next, and whether
  decision_support is ready.
- evidence_gap_diagnostics: structured booleans for missing inputs.

Does NOT fetch data, call providers, use LLMs, or make formal decisions.
analysis_plan is a deterministic artifact for the external host/agent
to consume, not an autonomous planner.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .context import CoreMetricsBundle, OptionalSummariesBundle, PortfolioInputBundle


def build_analysis_plan(
    *,
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle | None = None,
    optional: OptionalSummariesBundle | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    if diagnostics is None:
        diagnostics = {}
    if warnings is None:
        warnings = []
    available_inputs = _infer_available_inputs(bundle, metrics, optional)
    evidence_gap = _build_evidence_gap_diagnostics(bundle, metrics, optional)
    missing_inputs = [
        key for key, is_missing in evidence_gap.items()
        if is_missing and key != "details"
    ]
    blockers = _infer_blockers(evidence_gap, diagnostics)
    decision_support_ready = _compute_decision_support_ready(
        bundle, metrics, evidence_gap, diagnostics, blockers,
    )
    plan_warnings = _infer_warnings(evidence_gap, diagnostics, warnings)
    recommended_skills = _infer_recommended_skills(
        evidence_gap, user_goal, decision_support_ready,
    )
    recommended_mcp = _infer_recommended_mcp_capabilities(evidence_gap)
    evidence_requirements = _infer_evidence_requirements(evidence_gap)
    next_data_to_fetch = _infer_next_data_to_fetch(evidence_gap)

    return {
        "analysis_plan": {
            "user_goal": user_goal or "",
            "available_inputs": sorted(available_inputs),
            "missing_inputs": sorted(missing_inputs),
            "recommended_skill_sequence": recommended_skills,
            "recommended_mcp_capabilities": recommended_mcp,
            "evidence_requirements": evidence_requirements,
            "decision_support_ready": decision_support_ready,
            "blockers": sorted(blockers),
            "warnings": sorted(plan_warnings),
            "next_data_to_fetch": next_data_to_fetch,
        },
        "evidence_gap_diagnostics": evidence_gap,
    }


def _infer_available_inputs(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle | None,
    optional: OptionalSummariesBundle | None,
) -> list[str]:
    available: list[str] = []
    if bundle.positions:
        available.append("holdings")
    if bundle.transactions:
        available.append("transactions")
    if bundle.fund_profiles:
        available.append("fund_metadata")
    if bundle.fee_schedules:
        available.append("fee_schedule")
    if bundle.nav_history:
        available.append("nav_history")
    if bundle.benchmarks or bundle.benchmark_history:
        available.append("benchmark_data")
    if bundle.risk_profile:
        available.append("risk_preference")
    if bundle.constraints:
        available.append("user_constraints")
    if bundle.holdings:
        available.append("holdings_detail")
    if optional is not None:
        if optional.benchmark_summary is not None:
            available.append("benchmark_summary")
        if optional.peer_summary is not None:
            available.append("peer_summary")
        if optional.fee_summary is not None:
            available.append("fee_summary")
        if optional.redemption_summary is not None:
            available.append("redemption_summary")
        if optional.factor_summary is not None:
            available.append("factor_summary")
        if optional.manager_summary is not None:
            available.append("manager_summary")
    raw_payload = bundle.payload or {}
    if any(raw_payload.get(k) for k in ("news_evidence", "recent_news", "news_items")):
        available.append("recent_news")
    if any(raw_payload.get(k) for k in ("sentiment_evidence", "sentiment_snapshot")):
        available.append("sentiment")
    return available


def _build_evidence_gap_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle | None,
    optional: OptionalSummariesBundle | None,
) -> dict[str, Any]:
    missing_holdings = not bundle.positions
    missing_transaction_history = not bundle.transactions
    missing_fund_metadata = not bundle.fund_profiles
    missing_fee_schedule = not bundle.fee_schedules and not bundle.redemption_rules
    missing_nav_history = not bundle.nav_history or not bundle.nav_data
    missing_benchmark_data = not bundle.benchmarks and not bundle.benchmark_history
    raw_payload = bundle.payload or {}
    news_keys = ("news_evidence", "recent_news", "news_items")
    sentiment_keys = ("sentiment_evidence", "sentiment_snapshot")
    missing_recent_news = not any(
        raw_payload.get(k) for k in news_keys
    )
    missing_sentiment = not any(
        raw_payload.get(k) for k in sentiment_keys
    )
    missing_holdings_detail = not bundle.holdings
    missing_user_constraints = not bundle.constraints
    missing_risk_preference = not bundle.risk_profile

    details: list[dict[str, Any]] = []
    if missing_holdings:
        details.append({
            "code": "missing_holdings",
            "severity": "blocker",
            "recommended_next_data": "portfolio positions or holdings list",
        })
    if missing_transaction_history:
        details.append({
            "code": "missing_transaction_history",
            "severity": "warning",
            "recommended_next_data": "transaction ledger with BUY/SELL/DIVIDEND/FEE events",
        })
    if missing_fund_metadata:
        details.append({
            "code": "missing_fund_metadata",
            "severity": "warning",
            "recommended_next_data": "fund profile data (type, benchmark, manager, tags)",
        })
    if missing_fee_schedule:
        details.append({
            "code": "missing_fee_schedule",
            "severity": "warning",
            "recommended_next_data": "fee schedule and redemption rules",
        })
    if missing_nav_history:
        details.append({
            "code": "missing_nav_history",
            "severity": "warning",
            "recommended_next_data": "fund NAV history series",
        })
    if missing_benchmark_data:
        details.append({
            "code": "missing_benchmark_data",
            "severity": "warning",
            "recommended_next_data": "benchmark price history",
        })
    if missing_recent_news:
        details.append({
            "code": "missing_recent_news",
            "severity": "blocker",
            "recommended_next_data": "recent fund or theme news",
        })
    if missing_sentiment:
        details.append({
            "code": "missing_sentiment",
            "severity": "warning",
            "recommended_next_data": "sentiment snapshot for held funds or themes",
        })
    if missing_holdings_detail:
        details.append({
            "code": "missing_holdings_detail",
            "severity": "warning",
            "recommended_next_data": "fund holdings detail (stocks, bonds, weights)",
        })
    if missing_user_constraints:
        details.append({
            "code": "missing_user_constraints",
            "severity": "warning",
            "recommended_next_data": "user constraints (min trade, forbidden actions, planned holding period)",
        })
    if missing_risk_preference:
        details.append({
            "code": "missing_risk_preference",
            "severity": "warning",
            "recommended_next_data": "user risk preference (risk level, concentration limits, liquidity reserve)",
        })

    return {
        "missing_holdings": missing_holdings,
        "missing_transaction_history": missing_transaction_history,
        "missing_fund_metadata": missing_fund_metadata,
        "missing_fee_schedule": missing_fee_schedule,
        "missing_nav_history": missing_nav_history,
        "missing_benchmark_data": missing_benchmark_data,
        "missing_recent_news": missing_recent_news,
        "missing_sentiment": missing_sentiment,
        "missing_holdings_detail": missing_holdings_detail,
        "missing_user_constraints": missing_user_constraints,
        "missing_risk_preference": missing_risk_preference,
        "details": details,
    }


def _infer_blockers(
    evidence_gap: dict[str, Any],
    diagnostics: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if evidence_gap.get("missing_holdings"):
        blockers.append("missing_holdings")
    if evidence_gap.get("missing_recent_news"):
        blockers.append("missing_recent_news")
    if evidence_gap.get("missing_fee_schedule"):
        blockers.append("missing_fee_schedule")

    redemption_risk = diagnostics.get("redemption_fee_risk")
    if isinstance(redemption_risk, dict):
        affected = redemption_risk.get("affected_funds", [])
        if isinstance(affected, list) and affected:
            has_high_fee = False
            for item in affected:
                if not isinstance(item, dict):
                    continue
                fee_pct = item.get("fee_pct")
                if fee_pct is not None and float(fee_pct) > 0.01:
                    has_high_fee = True
                    break
            if has_high_fee:
                blockers.append("redemption_fee_blocker")

    return blockers


def _infer_warnings(
    evidence_gap: dict[str, Any],
    diagnostics: Mapping[str, Any],
    warnings: Sequence[str],
) -> list[str]:
    plan_warnings: list[str] = []
    if evidence_gap.get("missing_transaction_history"):
        plan_warnings.append("transaction_history_incomplete")
    if evidence_gap.get("missing_fund_metadata"):
        plan_warnings.append("fund_metadata_missing")
    if evidence_gap.get("missing_sentiment"):
        plan_warnings.append("sentiment_missing")
    if evidence_gap.get("missing_benchmark_data"):
        plan_warnings.append("benchmark_data_missing")
    if evidence_gap.get("missing_nav_history"):
        plan_warnings.append("nav_history_missing")
    if evidence_gap.get("missing_holdings_detail"):
        plan_warnings.append("holdings_detail_missing")
    if evidence_gap.get("missing_user_constraints"):
        plan_warnings.append("user_constraints_missing")
    if evidence_gap.get("missing_risk_preference"):
        plan_warnings.append("risk_preference_missing")

    theme_overweight = diagnostics.get("theme_overweight_diagnostics")
    if isinstance(theme_overweight, dict):
        overweight_themes = theme_overweight.get("overweight_themes", [])
        if isinstance(overweight_themes, list) and overweight_themes:
            plan_warnings.append("theme_overweight_warning")

    for w in warnings:
        if "stale" in w.lower():
            plan_warnings.append("evidence_stale")
            break

    return plan_warnings


def _infer_recommended_skills(
    evidence_gap: dict[str, Any],
    user_goal: str | None,
    decision_support_ready: bool,
) -> list[str]:
    skills: list[str] = ["fund_analysis"]
    if evidence_gap.get("missing_recent_news"):
        skills.append("news_research")
    if evidence_gap.get("missing_sentiment"):
        goal = (user_goal or "").lower()
        action_keywords = (
            "买", "卖", "加仓", "减仓", "止损", "止盈", "操作",
            "buy", "sell", "action", "trim", "add", "reduce",
            "趋势", "时机", "timing", "trend",
        )
        if any(kw in goal for kw in action_keywords):
            skills.append("sentiment_analysis")
    if not evidence_gap.get("missing_recent_news") and not evidence_gap.get("missing_holdings"):
        skills.append("thesis_generation")
    if decision_support_ready:
        skills.append("decision_support")
    return skills


def _infer_recommended_mcp_capabilities(
    evidence_gap: dict[str, Any],
) -> list[str]:
    caps: list[str] = []
    if evidence_gap.get("missing_fund_metadata"):
        caps.append("fund_metadata_lookup")
    if evidence_gap.get("missing_nav_history"):
        caps.append("fund_nav_history")
    if evidence_gap.get("missing_fee_schedule"):
        caps.append("fund_fee_schedule")
    if evidence_gap.get("missing_recent_news"):
        caps.append("market_news_search")
    if evidence_gap.get("missing_benchmark_data"):
        caps.append("benchmark_price_history")
    if evidence_gap.get("missing_sentiment"):
        caps.append("sentiment_snapshot")
    return sorted(caps)


def _infer_evidence_requirements(
    evidence_gap: dict[str, Any],
) -> list[str]:
    requirements: list[str] = []
    if evidence_gap.get("missing_holdings"):
        requirements.append("current holdings")
    if evidence_gap.get("missing_transaction_history"):
        requirements.append("transaction history")
    if evidence_gap.get("missing_fee_schedule"):
        requirements.append("fee schedule")
    if evidence_gap.get("missing_nav_history"):
        requirements.append("recent NAV series")
    if evidence_gap.get("missing_benchmark_data"):
        requirements.append("benchmark recent movement")
    if evidence_gap.get("missing_recent_news"):
        requirements.append("recent news evidence")
    if evidence_gap.get("missing_user_constraints"):
        requirements.append("user risk constraints")
    if evidence_gap.get("missing_risk_preference"):
        requirements.append("user risk preference")
    return requirements


def _infer_next_data_to_fetch(
    evidence_gap: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    if evidence_gap.get("missing_fee_schedule"):
        items.append("fund fee schedule")
    if evidence_gap.get("missing_nav_history"):
        items.append("fund NAV history")
    if evidence_gap.get("missing_benchmark_data"):
        items.append("recent benchmark movement")
    if evidence_gap.get("missing_recent_news"):
        items.append("recent fund news")
    if evidence_gap.get("missing_sentiment"):
        items.append("sentiment snapshot")
    if evidence_gap.get("missing_risk_preference"):
        items.append("user risk preference")
    if evidence_gap.get("missing_user_constraints"):
        items.append("liquidity needs and planned holding period")
    if evidence_gap.get("missing_fund_metadata"):
        items.append("fund profile metadata")
    if evidence_gap.get("missing_transaction_history"):
        items.append("transaction history")
    return items


def _compute_decision_support_ready(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle | None,
    evidence_gap: dict[str, Any],
    diagnostics: Mapping[str, Any],
    blockers: list[str],
) -> bool:
    if evidence_gap.get("missing_holdings"):
        return False
    if not metrics or not metrics.portfolio_summary:
        return False
    if evidence_gap.get("missing_recent_news"):
        return False
    if bool(blockers):
        return False
    return True
