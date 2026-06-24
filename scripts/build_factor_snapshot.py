#!/usr/bin/env python3
"""Build factor snapshot from portfolio input and optional data sources.

Purely deterministic calculation — NO network calls, NO API keys.
Reads portfolio_input (required), provider_snapshot (optional),
news_snapshot (optional), kg_context (optional).

Computes portfolio-level, holding-level, market/news factors with
confidence markers and data-quality tracking.

FORBIDDEN:
- No network calls
- No API keys
- No fabrication of missing data
- cost_basis=None MUST NOT become total_cost=0
- Missing units/nav MUST NOT be fabricated
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Risk bucket classification keywords (mirrors KG context builder)
# ---------------------------------------------------------------------------

_RISK_HIGH_KEYWORDS = {"半导体", "芯片", "创新药", "纳斯达克", "美股", "QDII", "电池", "油气", "CPO", "科技", "股票"}
_RISK_LOW_KEYWORDS = {"短债", "现金", "货币", "余额宝", "稳健", "理财", "纯债", "债券"}
_QDII_KEYWORDS = {"QDII", "海外", "全球", "国际", "美元", "纳斯达克", "标普"}
_EQUITY_KEYWORDS = {"股票", "混合", "成长", "价值", "指数", "半导体", "创新药", "科技", "消费"}
_BOND_CASH_KEYWORDS = {"债券", "纯债", "短债", "货币", "现金", "余额宝", "理财"}


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert to float, returning default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _classify_risk_bucket(tags: list[str], fund_name: str, sector: str) -> str:
    """Classify a holding's risk bucket from its tags/name/sector."""
    text = f"{' '.join(tags)} {fund_name} {sector}".lower()
    for kw in _RISK_HIGH_KEYWORDS:
        if kw.lower() in text:
            return "high"
    for kw in _RISK_LOW_KEYWORDS:
        if kw.lower() in text:
            return "low"
    return "medium"


def _is_qdii(tags: list[str], fund_name: str, sector: str) -> bool:
    text = f"{' '.join(tags)} {fund_name} {sector}".lower()
    return any(kw.lower() in text for kw in _QDII_KEYWORDS)


def _is_equity_like(tags: list[str], fund_name: str, sector: str) -> bool:
    text = f"{' '.join(tags)} {fund_name} {sector}".lower()
    return any(kw.lower() in text for kw in _EQUITY_KEYWORDS)


def _is_bond_cash(tags: list[str], fund_name: str, sector: str) -> bool:
    text = f"{' '.join(tags)} {fund_name} {sector}".lower()
    return any(kw.lower() in text for kw in _BOND_CASH_KEYWORDS)


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def build_factor_snapshot(
    portfolio_input: dict,
    provider_snapshot: dict | None = None,
    news_snapshot: dict | None = None,
    kg_context: dict | None = None,
) -> dict:
    """Build the factor snapshot dict.

    Handles missing values properly:
    - current_value missing is marked as None, NOT 0.0
    - Value-dependent factors are marked as missing when current_value is unavailable
    - Non-value factors (data completeness, profile coverage, etc.) are always computed
    """
    now = datetime.now(UTC).isoformat()

    holdings = portfolio_input.get("holdings", portfolio_input.get("positions", []))
    if not isinstance(holdings, list):
        holdings = []

    # ------------------------------------------------------------------
    # Holding-level factors
    # ------------------------------------------------------------------
    total_current_value: float | None = None  # None means unknown/missing
    known_cost_basis_total = 0.0
    known_cost_basis_count = 0
    cost_basis_missing_count = 0
    units_missing_count = 0
    nav_missing_count = 0
    current_value_missing_count = 0
    zero_value_count = 0  # Holdings with current_value explicitly 0

    # Build a map from fund_code → kg_context fund_entity for theme tags
    kg_fund_map: dict[str, dict] = {}
    if kg_context:
        for fe in kg_context.get("fund_entities", []):
            fc = fe.get("fund_code", "")
            if fc:
                kg_fund_map[fc] = fe

    holding_factors: list[dict] = []
    sector_concentration: defaultdict[str, float] = defaultdict(float)
    theme_concentration: defaultdict[str, float] = defaultdict(float)
    risk_bucket_exposure: defaultdict[str, float] = defaultdict(float)
    qdii_value = 0.0
    equity_value = 0.0
    bond_cash_value = 0.0
    short_term_trading_value = 0.0

    # Track holdings with known current_value for later summation
    holdings_with_value: list[tuple[int, dict]] = []

    for _idx, h in enumerate(holdings):
        if not isinstance(h, dict):
            continue

        fund_code = str(h.get("fund_code", h.get("code", "")))
        fund_name = str(h.get("fund_name", h.get("name", "")))

        # Check if current_value is explicitly provided (not just missing)
        current_value_raw = h.get("current_value")
        if current_value_raw is None:
            current_value_missing_count += 1
            current_value: float | None = None  # Mark as missing, NOT 0
        else:
            current_value = _safe_float(current_value_raw, 0.0)
            if current_value > 0:
                holdings_with_value.append((_idx, h))
            elif current_value == 0.0:
                zero_value_count += 1

        sector = str(h.get("sector", h.get("industry", "")))
        source_platform = str(h.get("source_platform", h.get("platform", "")))

        # Theme tags from KG context or holding
        kg_fe = kg_fund_map.get(fund_code, {})
        theme_tags = kg_fe.get("theme_tags", [])
        if not theme_tags:
            theme_raw = h.get("theme", "")
            if isinstance(theme_raw, str) and theme_raw:
                theme_tags = [t.strip() for t in theme_raw.split(",") if t.strip()]
            elif isinstance(theme_raw, list):
                theme_tags = [str(t).strip() for t in theme_raw if t]

        # Risk bucket
        risk_bucket = (
            h.get("risk_bucket", "")
            or kg_fe.get("risk_bucket", "")
            or _classify_risk_bucket(theme_tags, fund_name, sector)
        )

        # Cost basis — careful: None must NOT become 0
        cost_basis_raw = h.get("cost_basis", h.get("total_cost", None))
        known_cost_basis: float | None = None
        cost_basis_confidence: str = "missing"
        cost_basis_missing = False

        if cost_basis_raw is not None:
            try:
                known_cost_basis = float(cost_basis_raw)
                cost_basis_confidence = "high"
            except (TypeError, ValueError):
                cost_basis_confidence = "unparseable"
                cost_basis_missing = True
        else:
            cost_basis_missing = True

        # Units / shares
        units_raw = h.get("units", h.get("shares", None))
        units_missing = units_raw is None

        # NAV
        nav_raw = h.get("nav", None)
        nav_missing = nav_raw is None

        # Unrealized gain/loss - only computable if we have both current_value and cost_basis
        unrealized_gain_loss_amount: float | None = None
        unrealized_gain_loss_pct: float | None = None
        if current_value is not None and known_cost_basis is not None and known_cost_basis != 0 and current_value > 0:
            unrealized_gain_loss_amount = round(current_value - known_cost_basis, 2)
            unrealized_gain_loss_pct = round((current_value - known_cost_basis) / known_cost_basis, 6)

        # Track cost basis for portfolio total (only known values)
        if not cost_basis_missing and known_cost_basis is not None:
            known_cost_basis_total += known_cost_basis
            known_cost_basis_count += 1
        else:
            cost_basis_missing_count += 1

        if units_missing:
            units_missing_count += 1
        if nav_missing:
            nav_missing_count += 1

        # Build holding factor record - current_value is None if missing
        hf: dict[str, Any] = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "current_value": round(current_value, 2) if current_value is not None else None,
            "current_value_missing": current_value is None,
            "weight": None,  # filled later if we have total_value
            "known_cost_basis": round(known_cost_basis, 2) if known_cost_basis is not None else None,
            "unrealized_gain_loss_amount": unrealized_gain_loss_amount,
            "unrealized_gain_loss_pct": unrealized_gain_loss_pct,
            "cost_basis_confidence": cost_basis_confidence,
            "units_missing": units_missing,
            "nav_missing": nav_missing,
            "cost_basis_missing": cost_basis_missing,
            "risk_bucket": risk_bucket,
            "theme_tags": theme_tags,
            "source_platform": source_platform,
        }
        holding_factors.append(hf)

        # Track sector/theme concentrations (only for holdings with known current_value)
        if current_value is not None and current_value > 0:
            if sector:
                sector_concentration[sector] += current_value
            for tag in theme_tags:
                theme_concentration[tag] += current_value
            risk_bucket_exposure[risk_bucket] += current_value

            # QDII / overseas
            if _is_qdii(theme_tags, fund_name, sector):
                qdii_value += current_value

            # Equity-like
            if _is_equity_like(theme_tags, fund_name, sector):
                equity_value += current_value

            # Bond/cash
            if _is_bond_cash(theme_tags, fund_name, sector):
                bond_cash_value += current_value

        # Short-term trading bucket (pending_amount)
        pending = _safe_float(h.get("pending_amount", 0))
        short_term_trading_value += pending

    # ------------------------------------------------------------------
    # Calculate total_current_value from holdings with known values
    # ------------------------------------------------------------------
    if holdings_with_value:
        total_current_value = sum(h[1].get("current_value", 0) for h in holdings_with_value)
        total_current_value = round(total_current_value, 2)
    else:
        total_current_value = None  # Unknown, not 0

    # ------------------------------------------------------------------
    # 80% heuristic: if most holdings have current_value=0 or None,
    # treat the zeros as "likely missing" rather than "known to be zero"
    # ------------------------------------------------------------------
    current_value_likely_missing = False
    total_holdings = len(holding_factors)
    if total_holdings > 0:
        likely_missing_count = zero_value_count + current_value_missing_count
        if likely_missing_count / total_holdings >= 0.8:
            current_value_likely_missing = True
            total_current_value = None  # Override: treat as unknown

    # ------------------------------------------------------------------
    # Normalize weights and concentrations
    # ------------------------------------------------------------------
    if total_current_value is not None and total_current_value > 0:
        for hf in holding_factors:
            if hf["current_value"] is not None:
                hf["weight"] = round(hf["current_value"] / total_current_value, 6)
            else:
                hf["weight"] = None  # Cannot calculate weight without current_value

        for k in sector_concentration:
            sector_concentration[k] = round(sector_concentration[k] / total_current_value, 6)
        for k in theme_concentration:
            theme_concentration[k] = round(theme_concentration[k] / total_current_value, 6)
        for k in risk_bucket_exposure:
            risk_bucket_exposure[k] = round(risk_bucket_exposure[k] / total_current_value, 6)

        qdii_ratio = round(qdii_value / total_current_value, 6)
        equity_ratio = round(equity_value / total_current_value, 6)
        bond_cash_ratio = round(bond_cash_value / total_current_value, 6)
        short_term_ratio = round(short_term_trading_value / total_current_value, 6)

        # Cash ratio
        cash_available = _safe_float(portfolio_input.get("cash_available", 0))
        cash_ratio = round(cash_available / total_current_value, 6)

        # Single position weight
        weights_with_value = [hf["weight"] for hf in holding_factors if hf["weight"] is not None]
        single_max_weight = max(weights_with_value) if weights_with_value else None

        # Top-N concentration
        sorted_weights = sorted([w for w in weights_with_value if w is not None], reverse=True)
        top3 = round(sum(sorted_weights[:3]), 6) if sorted_weights else None
        top5 = round(sum(sorted_weights[:5]), 6) if sorted_weights else None
    else:
        qdii_ratio = None  # Cannot calculate without total_value
        equity_ratio = None
        bond_cash_ratio = None
        short_term_ratio = None
        cash_ratio = None
        single_max_weight = None
        top3 = None
        top5 = None

    # ------------------------------------------------------------------
    # Portfolio-level factors
    # ------------------------------------------------------------------
    portfolio_factors: dict[str, Any] = {
        "total_current_value": total_current_value,
        "total_current_value_missing": total_current_value is None,
        "known_cost_basis_total": round(known_cost_basis_total, 2) if known_cost_basis_total > 0 else None,
        "cost_basis_missing_count": cost_basis_missing_count,
        "cash_ratio": cash_ratio,
        "cash_ratio_missing": cash_ratio is None,
        "risky_asset_ratio": round(risk_bucket_exposure.get("high", 0.0), 6) if total_current_value else None,
        "low_risk_asset_ratio": round(risk_bucket_exposure.get("low", 0.0), 6) if total_current_value else None,
        "sector_concentration": dict(sector_concentration) if sector_concentration else None,
        "theme_concentration": dict(theme_concentration) if theme_concentration else None,
        "single_position_weight": single_max_weight,
        "top_3_concentration": top3,
        "top_5_concentration": top5,
        "qdii_overseas_exposure": qdii_ratio,
        "equity_like_exposure": equity_ratio,
        "bond_cash_exposure": bond_cash_ratio,
        "short_term_trading_bucket_exposure": short_term_ratio,
    }

    # ------------------------------------------------------------------
    # Data completeness factors (always computed, even without current_value)
    # ------------------------------------------------------------------
    valuation_type_counts: dict[str, int] = {"estimated": 0, "cashflow_only": 0, "none": 0}
    for h in holdings:
        if isinstance(h, dict):
            vt = str(h.get("valuation_type", "none"))
            if vt in valuation_type_counts:
                valuation_type_counts[vt] += 1
            else:
                valuation_type_counts[vt] = valuation_type_counts.get(vt, 0) + 1

    data_completeness_factors: dict[str, Any] = {
        "holdings_count": len(holdings),
        "holdings_with_current_value": len(holdings_with_value),
        "holdings_without_current_value": current_value_missing_count,
        "cost_basis_complete_count": known_cost_basis_count,
        "cost_basis_missing_count": cost_basis_missing_count,
        "units_complete_count": len(holdings) - units_missing_count,
        "units_missing_count": units_missing_count,
        "nav_complete_count": len(holdings) - nav_missing_count,
        "nav_missing_count": nav_missing_count,
        "valuation_type_counts": valuation_type_counts,
    }

    # Profile coverage from kg_context
    profile_coverage: dict[str, Any] = {
        "kg_context_available": kg_context is not None,
        "fund_entities_count": len(kg_context.get("fund_entities", [])) if kg_context else 0,
        "entities_count": len(kg_context.get("entities", [])) if kg_context else 0,
    }
    if kg_context:
        dq = kg_context.get("data_quality", {})
        profile_coverage.update(
            {
                "provider_snapshot_available": dq.get("provider_snapshot_available", False),
                "fund_profiles_available": dq.get("fund_profiles_available", False),
                "fund_holdings_available": dq.get("fund_holdings_available", False),
                "benchmark_available": dq.get("benchmark_available", False),
            }
        )

    # ------------------------------------------------------------------
    # Market / news factors (from news_snapshot if available)
    # ------------------------------------------------------------------
    market_factors: dict[str, Any] = {}
    news_factors: dict[str, Any] = {}

    if news_snapshot:
        items = news_snapshot.get("items", [])

        # News count by entity
        news_count_by_entity: dict[str, int] = Counter()
        for item in items:
            for ent in item.get("related_entities", []):
                news_count_by_entity[ent] += 1

        # News count by topic
        news_count_by_topic: dict[str, int] = Counter()
        for item in items:
            for tag in item.get("topic_tags", []):
                news_count_by_topic[tag] += 1

        # News count by query_type
        news_count_by_query_type: dict[str, int] = Counter()
        for item in items:
            qt = item.get("query_type", "unknown")
            news_count_by_query_type[qt] += 1

        # Fallback vs specific query news
        fallback_news_count = sum(1 for item in items if item.get("is_fallback_query", False))
        specific_news_count = len(items) - fallback_news_count

        # Stale news by topic (freshness < 0.2)
        stale_by_topic: dict[str, int] = Counter()
        for item in items:
            if item.get("freshness_score", 1.0) < 0.2:
                for tag in item.get("topic_tags", []):
                    stale_by_topic[tag] += 1

        # Provider coverage score
        provider_status = news_snapshot.get("provider_status", {})
        available_providers = sum(1 for ps in provider_status.values() if ps.get("available", False))
        provider_coverage_score = round(available_providers / max(len(provider_status), 1), 4)

        # Negative risk signal count (heuristic: low freshness + low relevance)
        negative_risk_signal_count = sum(
            1 for item in items if item.get("freshness_score", 1.0) < 0.3 and item.get("relevance_score", 0.5) > 0.7
        )

        # Positive catalyst count (heuristic: high freshness + high relevance)
        positive_catalyst_count = sum(
            1 for item in items if item.get("freshness_score", 0.0) > 0.6 and item.get("relevance_score", 0.0) > 0.7
        )

        news_factors = {
            "total_news_items": len(items),
            "news_count_by_entity": dict(news_count_by_entity),
            "news_count_by_topic": dict(news_count_by_topic),
            "news_count_by_query_type": dict(news_count_by_query_type),
            "fallback_query_news_count": fallback_news_count,
            "specific_query_news_count": specific_news_count,
            "stale_news_by_topic": dict(stale_by_topic),
            "provider_coverage_score": provider_coverage_score,
            "negative_risk_signal_count": negative_risk_signal_count,
            "positive_catalyst_count": positive_catalyst_count,
        }
    else:
        news_factors = {
            "total_news_items": 0,
            "news_count_by_entity": {},
            "news_count_by_topic": {},
            "news_count_by_query_type": {},
            "fallback_query_news_count": 0,
            "specific_query_news_count": 0,
            "stale_news_by_topic": {},
            "provider_coverage_score": 0.0,
            "negative_risk_signal_count": 0,
            "positive_catalyst_count": 0,
        }

    # Market factors from provider_snapshot if available
    if provider_snapshot:
        market_factors = {
            "provider_data_available": True,
            "nav_update_available": bool(provider_snapshot.get("nav_data")),
            "benchmark_available": bool(provider_snapshot.get("benchmark_data")),
        }
    else:
        market_factors = {
            "provider_data_available": False,
            "nav_update_available": False,
            "benchmark_available": False,
        }

    # ------------------------------------------------------------------
    # Data quality
    # ------------------------------------------------------------------
    cost_basis_partial = cost_basis_missing_count > 0 and cost_basis_missing_count < len(holding_factors)
    news_snapshot_missing = news_snapshot is None
    provider_snapshot_missing = provider_snapshot is None

    # Factor confidence - based on data completeness
    missing_count = cost_basis_missing_count + units_missing_count + nav_missing_count + current_value_missing_count
    total_possible = len(holding_factors) * 4  # 4 fields per holding
    if total_possible == 0 or missing_count == 0:
        factor_confidence = "high"
    elif missing_count <= total_possible * 0.3:
        factor_confidence = "medium"
    else:
        factor_confidence = "low"

    data_quality: dict[str, Any] = {
        "cost_basis_partial": cost_basis_partial,
        "cost_basis_missing_count": cost_basis_missing_count,
        "units_missing_count": units_missing_count,
        "nav_missing_count": nav_missing_count,
        "current_value_missing_count": current_value_missing_count,
        "zero_value_count": zero_value_count,
        "current_value_likely_missing": current_value_likely_missing,
        "news_snapshot_missing": news_snapshot_missing,
        "provider_snapshot_missing": provider_snapshot_missing,
        "factor_confidence": factor_confidence,
        "value_factors_available": total_current_value is not None,
        "uncertainty_note": "市值权重/收益率/仓位贡献无法计算，因为当前市值数据缺失"
        if total_current_value is None
        else None,
    }

    return {
        "snapshot_type": "factor_snapshot",
        "generated_at": now,
        "portfolio_factors": portfolio_factors,
        "holding_factors": holding_factors,
        "data_completeness_factors": data_completeness_factors,
        "profile_coverage": profile_coverage,
        "market_factors": market_factors,
        "news_factors": news_factors,
        "data_quality": data_quality,
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build factor snapshot from portfolio data (deterministic, no network)."
    )
    parser.add_argument(
        "--portfolio-input",
        required=True,
        type=Path,
        help="Path to portfolio_input.private.json (required)",
    )
    parser.add_argument(
        "--provider-snapshot",
        type=Path,
        default=None,
        help="Path to provider_data_snapshot.private.json (optional)",
    )
    parser.add_argument(
        "--news-snapshot",
        type=Path,
        default=None,
        help="Path to news_snapshot.private.json (optional)",
    )
    parser.add_argument(
        "--kg-context",
        type=Path,
        default=None,
        help="Path to knowledge_graph_context.private.json (optional)",
    )
    parser.add_argument(
        "--fund-profile-snapshot",
        type=Path,
        default=None,
        help="Path to fund_profile_snapshot.private.json (optional, read-only for profile enrichment)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for factor_snapshot.private.json",
    )

    args = parser.parse_args(argv)

    # Read required input
    portfolio_input = _read_json(args.portfolio_input)
    if portfolio_input is None:
        print(f"ERROR: Required file not found: {args.portfolio_input}", file=sys.stderr)
        return 1

    # Read optional inputs
    provider_snapshot = _read_json(args.provider_snapshot) if args.provider_snapshot else None
    news_snapshot = _read_json(args.news_snapshot) if args.news_snapshot else None
    kg_context = _read_json(args.kg_context) if args.kg_context else None
    # fund_profile_snapshot read for future profile enrichment (passthrough)
    if args.fund_profile_snapshot:
        _read_json(args.fund_profile_snapshot)  # noqa: F841 — passthrough placeholder

    # Build snapshot
    result = build_factor_snapshot(
        portfolio_input=portfolio_input,
        provider_snapshot=provider_snapshot,
        news_snapshot=news_snapshot,
        kg_context=kg_context,
    )

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: factor snapshot written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
