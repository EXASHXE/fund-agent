#!/usr/bin/env python3
"""Build knowledge graph context snapshot from portfolio input and optional data sources.

Reads portfolio_input.private.json (required), manual_transactions.private.csv
(optional), and provider_data_snapshot.private.json (optional).  Produces a
knowledge_graph_context.private.json with entities, watch topics, query plan,
and missing-data markers.

FORBIDDEN:
- No network requests
- No API key usage
- No guessing/auto-completing unknown fund codes
- No modification of source files
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Entity types for KG
# ---------------------------------------------------------------------------

ENTITY_TYPES = [
    "fund",
    "fund_name",
    "fund_code",
    "fund_profile",
    "fund_manager",
    "benchmark",
    "index",
    "holding_company",
    "holding_ticker",
    "industry",
    "region",
    "asset_class",
    "risk_bucket",
    "theme",
    "macro",
]

# Query type priorities (lower number = higher priority)
QUERY_TYPE_PRIORITY = {
    "holding_company": 1,
    "holding_ticker": 1,
    "benchmark": 1,
    "tracking_index": 1,
    "fund_profile": 2,
    "fund_manager": 2,
    "top_industry": 2,
    "top_region": 2,
    "sector": 3,
    "theme": 3,
    "macro": 4,
    "theme_fallback": 5,
}

# Watch topics and keyword mappings
# ---------------------------------------------------------------------------

WATCH_TOPICS = [
    "半导体",
    "CPO",
    "创新药",
    "ASCO",
    "QDII",
    "纳斯达克",
    "红利低波",
    "短债",
    "标普500",
    "油气",
    "电池",
    "现金/余额宝/稳健理财",
]

# topic → list of keywords that indicate a holding relates to this topic
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "集成电路", "晶圆", "封测", "光刻"],
    "CPO": ["CPO", "光模块", "光通信", "光电"],
    "创新药": ["创新药", "医药", "生物", "药", "医疗", "临床"],
    "ASCO": ["ASCO", "肿瘤", "抗癌", "oncology"],
    "QDII": ["QDII", "海外", "全球", "国际", "美元"],
    "纳斯达克": ["纳斯达克", "NASDAQ", "纳指", "美股", "科技股"],
    "红利低波": ["红利", "低波", "高股息", "分红", "价值"],
    "短债": ["短债", "债券", "纯债", "利率债", "信用债"],
    "标普500": ["标普", "S&P", "SP500", "500"],
    "油气": ["油气", "石油", "原油", "OPEC", "能源", "天然气"],
    "电池": ["电池", "锂电", "储能", "钠电", "固态电池", "新能源车"],
    "现金/余额宝/稳健理财": ["现金", "余额宝", "货币", "理财", "稳健"],
}

# Risk bucket classification keywords
_RISK_BUCKET_KEYWORDS: dict[str, list[str]] = {
    "high": ["半导体", "芯片", "创新药", "纳斯达克", "美股", "QDII", "电池", "油气", "CPO", "科技"],
    "medium": ["红利", "消费", "医药", "金融", "银行"],
    "low": ["短债", "现金", "货币", "余额宝", "稳健", "理财", "纯债"],
}


def _match_topics(fund_name: str, fund_code: str, sector: str) -> list[str]:
    """Match a holding to watch topics based on keywords in name/code/sector."""
    text = f"{fund_name} {fund_code} {sector}".lower()
    matched: list[str] = []
    for topic, keywords in _TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(topic)
                break
    return matched


def _infer_risk_bucket(fund_name: str, sector: str, theme_tags: list[str]) -> str:
    """Infer risk bucket from keywords. Returns 'unknown' if indeterminate."""
    text = f"{fund_name} {sector} {' '.join(theme_tags)}".lower()
    for bucket, keywords in _RISK_BUCKET_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return bucket
    return "unknown"


def _stable_hash(text: str) -> str:
    """Return a short stable hex hash for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Fund profile and holdings extraction from provider_snapshot
# ---------------------------------------------------------------------------


def _extract_fund_profiles(provider_snapshot: dict | None) -> dict[str, dict]:
    """Extract fund profiles from provider_snapshot.

    Returns a dict mapping fund_name -> profile data.
    """
    if not provider_snapshot:
        return {}

    profiles = {}
    fund_profiles_list = provider_snapshot.get("fund_profiles", [])
    if not isinstance(fund_profiles_list, list):
        fund_profiles_list = []

    for fp in fund_profiles_list:
        if not isinstance(fp, dict):
            continue
        fund_name = fp.get("fund_name", "")
        if fund_name:
            profiles[fund_name] = fp

    return profiles


def _extract_fund_holdings(provider_snapshot: dict | None) -> dict[str, list[dict]]:
    """Extract fund holdings from provider_snapshot.

    Returns a dict mapping fund_name -> list of holdings.
    """
    if not provider_snapshot:
        return {}

    holdings_map = {}
    fund_holdings_list = provider_snapshot.get("fund_holdings", [])
    if not isinstance(fund_holdings_list, list):
        fund_holdings_list = []

    for fh in fund_holdings_list:
        if not isinstance(fh, dict):
            continue
        fund_name = fh.get("fund_name", "")
        if fund_name:
            if fund_name not in holdings_map:
                holdings_map[fund_name] = []
            holdings_map[fund_name].append(fh)

    return holdings_map


def _extract_benchmark_index(provider_snapshot: dict | None) -> dict[str, str]:
    """Extract benchmark/index info from provider_snapshot.

    Returns a dict mapping fund_name -> benchmark/index name.
    """
    if not provider_snapshot:
        return {}

    benchmark_map = {}
    fund_profiles_list = provider_snapshot.get("fund_profiles", [])
    if not isinstance(fund_profiles_list, list):
        fund_profiles_list = []

    for fp in fund_profiles_list:
        if not isinstance(fp, dict):
            continue
        fund_name = fp.get("fund_name", "")
        benchmark = fp.get("benchmark", "")
        tracking_index = fp.get("tracking_index", "")
        if fund_name and (benchmark or tracking_index):
            benchmark_map[fund_name] = benchmark or tracking_index

    return benchmark_map


# ---------------------------------------------------------------------------
# Entity and query plan building
# ---------------------------------------------------------------------------


def _build_entity(
    entity_type: str,
    label: str,
    source: str = "portfolio_input",
    confidence: str = "medium",
    related_funds: list[str] | None = None,
    data_quality_flags: list[str] | None = None,
    **kwargs,
) -> dict:
    """Build a KG entity with full metadata."""
    entity_id = f"{entity_type}:{label}"
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "label": label,
        "aliases": kwargs.get("aliases", []),
        "source": source,
        "confidence": confidence,
        "related_funds": related_funds or [],
        "evidence_refs": kwargs.get("evidence_refs", []),
        "data_quality_flags": data_quality_flags or [],
    }


def _build_query_plan_entry(
    query: str,
    query_type: str,
    entities: list[str],
    related_funds: list[str] | None = None,
    reason: str = "",
    source: str = "portfolio_input",
    confidence: str = "medium",
    priority: int | None = None,
) -> dict:
    """Build a query plan entry with full metadata."""
    if priority is None:
        priority = QUERY_TYPE_PRIORITY.get(query_type, 5)

    return {
        "query_id": _stable_hash(f"q_{query}"),
        "query": query,
        "query_type": query_type,
        "priority": priority,
        "entities": entities,
        "related_funds": related_funds or [],
        "reason": reason,
        "source": source,
        "confidence": confidence,
        "fallback": query_type == "theme_fallback",
    }


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def build_kg_context(
    portfolio_input: dict,
    manual_transactions: list[dict] | None = None,
    provider_snapshot: dict | None = None,
) -> dict:
    """Build the knowledge graph context snapshot dict."""
    now = datetime.now(UTC).isoformat()

    holdings = portfolio_input.get("holdings", portfolio_input.get("positions", []))
    if not isinstance(holdings, list):
        holdings = []

    # Extract provider data
    fund_profiles = _extract_fund_profiles(provider_snapshot)
    fund_holdings = _extract_fund_holdings(provider_snapshot)
    benchmark_map = _extract_benchmark_index(provider_snapshot)

    # Portfolio summary
    total_value = 0.0
    for h in holdings:
        with contextlib.suppress(TypeError, ValueError):
            total_value += float(h.get("current_value", 0))

    entities: list[dict] = []
    fund_entities: list[dict] = []
    query_plan: list[dict] = []
    missing_data: dict = {
        "fund_code_missing": [],
        "units_missing": [],
        "nav_missing": [],
        "cost_basis_missing": [],
        "provider_snapshot_missing": provider_snapshot is None,
        "manual_transactions_missing": manual_transactions is None,
        "fund_profiles_missing": len(fund_profiles) == 0,
        "fund_holdings_missing": len(fund_holdings) == 0,
        "benchmark_missing": [],
    }

    seen_entity_ids: set[str] = set()

    # Track data quality flags
    data_quality_flags: list[str] = []
    if provider_snapshot is None:
        data_quality_flags.append("provider_snapshot_missing")
    if not fund_profiles:
        data_quality_flags.append("fund_profiles_missing")
    if not fund_holdings:
        data_quality_flags.append("fund_holdings_missing")

    for idx, h in enumerate(holdings):
        if not isinstance(h, dict):
            continue

        fund_name = str(h.get("fund_name", h.get("name", "")))
        fund_code = h.get("fund_code", h.get("code", ""))
        fund_code = str(fund_code) if fund_code else ""
        sector = str(h.get("sector", h.get("industry", "")))
        theme = h.get("theme", "")

        # Get fund profile and holdings from provider
        profile = fund_profiles.get(fund_name, {})
        holdings_list = fund_holdings.get(fund_name, [])
        benchmark = benchmark_map.get(fund_name, "")

        # Track missing benchmark
        if not benchmark and fund_name:
            missing_data["benchmark_missing"].append(fund_name)

        # Extract theme_tags
        theme_tags: list[str] = []
        if isinstance(theme, str) and theme:
            theme_tags = [t.strip() for t in theme.split(",") if t.strip()]
        elif isinstance(theme, list):
            theme_tags = [str(t).strip() for t in theme if t]

        # Add declared theme tags from profile
        declared_tags = profile.get("declared_theme_tags", [])
        if declared_tags:
            for tag in declared_tags:
                if tag not in theme_tags:
                    theme_tags.append(tag)

        # Match watch topics
        matched_topics = _match_topics(fund_name, fund_code, sector)
        # Add theme-derived topics
        for tag in theme_tags:
            for topic in WATCH_TOPICS:
                if (tag in topic or topic in tag) and topic not in matched_topics:
                    matched_topics.append(topic)

        # Infer risk bucket
        risk_bucket = h.get("risk_bucket", "") or _infer_risk_bucket(fund_name, sector, matched_topics)

        # Determine confidence based on data availability
        confidence = "low"
        if profile:
            profile_confidence = profile.get("profile_confidence", "medium")
            if profile_confidence in ("high", "medium", "low"):
                confidence = profile_confidence
        if holdings_list:
            confidence = "high"

        # Build entities
        related_funds = [fund_name] if fund_name else []

        if fund_code:
            ent = _build_entity("fund", fund_code, confidence=confidence, related_funds=related_funds)
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])
        if fund_name:
            ent = _build_entity("fund_name", fund_name, confidence=confidence, related_funds=related_funds)
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])
        if sector:
            ent = _build_entity("industry", sector, confidence="medium", related_funds=related_funds)
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])

        # Add benchmark/index entities
        if benchmark:
            ent = _build_entity(
                "benchmark",
                benchmark,
                source="provider_snapshot",
                confidence="high",
                related_funds=related_funds,
            )
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])

        # Add holding company entities from provider holdings
        for holding in holdings_list[:5]:  # Top 5 holdings
            holding_name = holding.get("name", "")
            holding_ticker = holding.get("ticker", "")
            holding_sector = holding.get("sector", "")
            holding_confidence = holding.get("confidence", "medium")
            holding_source = holding.get("source", "provider_snapshot")

            if holding_name:
                ent = _build_entity(
                    "holding_company",
                    holding_name,
                    source=holding_source,
                    confidence=holding_confidence,
                    related_funds=related_funds,
                )
                if ent["entity_id"] not in seen_entity_ids:
                    entities.append(ent)
                    seen_entity_ids.add(ent["entity_id"])

                # Add sector entity for holding
                if holding_sector:
                    sector_ent = _build_entity(
                        "industry",
                        holding_sector,
                        source=holding_source,
                        confidence=holding_confidence,
                        related_funds=related_funds,
                    )
                    if sector_ent["entity_id"] not in seen_entity_ids:
                        entities.append(sector_ent)
                        seen_entity_ids.add(sector_ent["entity_id"])

            if holding_ticker:
                ent = _build_entity(
                    "holding_ticker",
                    holding_ticker,
                    source=holding_source,
                    confidence=holding_confidence,
                    related_funds=related_funds,
                )
                if ent["entity_id"] not in seen_entity_ids:
                    entities.append(ent)
                    seen_entity_ids.add(ent["entity_id"])

        # Add fund manager entity
        fund_manager = profile.get("fund_manager", "")
        if fund_manager:
            ent = _build_entity(
                "fund_manager",
                fund_manager,
                source="provider_snapshot",
                confidence="medium",
                related_funds=related_funds,
            )
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])

        # Add macro/topic entities
        for topic in matched_topics:
            ent = _build_entity("macro", topic, source="derived", confidence="low", related_funds=related_funds)
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])
        if risk_bucket and risk_bucket != "unknown":
            ent = _build_entity(
                "risk_bucket", risk_bucket, source="derived", confidence="medium", related_funds=related_funds
            )
            if ent["entity_id"] not in seen_entity_ids:
                entities.append(ent)
                seen_entity_ids.add(ent["entity_id"])

        # Fund entity record with enhanced data
        fund_ent: dict[str, Any] = {
            "fund_code": fund_code or "",
            "fund_name": fund_name,
            "sector": sector,
            "theme_tags": matched_topics,
            "risk_bucket": risk_bucket,
            "confidence": confidence,
            "data_quality_flags": [],
        }

        # Add profile data to fund entity
        if profile:
            fund_ent["fund_type"] = profile.get("fund_type", "")
            fund_ent["benchmark"] = benchmark
            fund_ent["tracking_index"] = profile.get("tracking_index", "")
            fund_ent["fund_manager"] = fund_manager
            fund_ent["investment_scope"] = profile.get("investment_scope", "")
            fund_ent["declared_theme_tags"] = profile.get("declared_theme_tags", [])

        # Add holdings data to fund entity
        if holdings_list:
            fund_ent["top_holdings"] = [
                {
                    "name": h.get("name", ""),
                    "ticker": h.get("ticker", ""),
                    "market": h.get("market", ""),
                    "asset_type": h.get("asset_type", ""),
                    "weight": h.get("weight"),
                    "sector": h.get("sector", ""),
                    "confidence": h.get("confidence", "medium"),
                }
                for h in holdings_list[:5]
            ]
            fund_ent["holdings_confidence"] = "high"
        else:
            fund_ent["top_holdings"] = []
            fund_ent["holdings_confidence"] = "missing"

        fund_entities.append(fund_ent)

        # Missing data tracking
        if not fund_code:
            missing_data["fund_code_missing"].append(fund_name or f"holding_{idx}")
        if h.get("units") is None or h.get("shares") is None:
            # Only flag if the field is expected but absent
            if "units" in h or "shares" in h:
                pass  # present but may be None
            else:
                missing_data["units_missing"].append(fund_code or fund_name or f"holding_{idx}")
        if h.get("nav") is None and "nav" in h:
            missing_data["nav_missing"].append(fund_code or fund_name or f"holding_{idx}")
        if h.get("cost_basis") is None and h.get("total_cost") is None and ("cost_basis" in h or "total_cost" in h):
            missing_data["cost_basis_missing"].append(fund_code or fund_name or f"holding_{idx}")

        # Build query plan entries with priorities

        # Priority 1: Holding company queries (from provider holdings)
        for holding in holdings_list[:5]:
            holding_name = holding.get("name", "")
            holding_ticker = holding.get("ticker", "")
            if holding_name:
                query_plan.append(
                    _build_query_plan_entry(
                        query=holding_name,
                        query_type="holding_company",
                        entities=[f"holding_company:{holding_name}"],
                        related_funds=related_funds,
                        reason=f"Top holding of {fund_name}",
                        source="provider_snapshot",
                        confidence=holding.get("confidence", "medium"),
                    )
                )
            if holding_ticker:
                query_plan.append(
                    _build_query_plan_entry(
                        query=holding_ticker,
                        query_type="holding_ticker",
                        entities=[f"holding_ticker:{holding_ticker}"],
                        related_funds=related_funds,
                        reason=f"Ticker for {holding.get('name', holding_ticker)}",
                        source="provider_snapshot",
                        confidence=holding.get("confidence", "medium"),
                    )
                )

        # Priority 1: Benchmark/index queries
        if benchmark:
            query_plan.append(
                _build_query_plan_entry(
                    query=benchmark,
                    query_type="benchmark",
                    entities=[f"benchmark:{benchmark}"],
                    related_funds=related_funds,
                    reason=f"Benchmark for {fund_name}",
                    source="provider_snapshot",
                    confidence="high",
                )
            )

        # Priority 2: Fund profile queries
        if profile:
            if fund_manager:
                query_plan.append(
                    _build_query_plan_entry(
                        query=fund_manager,
                        query_type="fund_manager",
                        entities=[f"fund_manager:{fund_manager}"],
                        related_funds=related_funds,
                        reason=f"Fund manager of {fund_name}",
                        source="provider_snapshot",
                        confidence="medium",
                    )
                )
            if profile.get("investment_scope"):
                query_plan.append(
                    _build_query_plan_entry(
                        query=profile["investment_scope"],
                        query_type="fund_profile",
                        entities=[f"fund_profile:{fund_name}"],
                        related_funds=related_funds,
                        reason=f"Investment scope of {fund_name}",
                        source="provider_snapshot",
                        confidence="medium",
                    )
                )

        # Priority 3: Sector/theme queries
        if sector:
            query_plan.append(
                _build_query_plan_entry(
                    query=sector,
                    query_type="sector",
                    entities=[f"industry:{sector}"],
                    related_funds=related_funds,
                    reason=f"Sector of {fund_name}",
                    source="portfolio_input",
                    confidence="medium",
                )
            )
        for topic in matched_topics:
            query_plan.append(
                _build_query_plan_entry(
                    query=topic,
                    query_type="theme",
                    entities=[f"macro:{topic}"],
                    related_funds=related_funds,
                    reason=f"Theme tag for {fund_name}",
                    source="derived",
                    confidence="low",
                )
            )

    # Deduplicate query plan by query_id
    seen_qids: set[str] = set()
    deduped_plan: list[dict] = []
    for q in query_plan:
        if q["query_id"] not in seen_qids:
            deduped_plan.append(q)
            seen_qids.add(q["query_id"])

    # Add macro-level queries for unmatched watch topics (Priority 5 - fallback)
    matched_topic_set: set[str] = set()
    for fe in fund_entities:
        for t in fe["theme_tags"]:
            matched_topic_set.add(t)

    for topic in WATCH_TOPICS:
        if topic not in matched_topic_set:
            deduped_plan.append(
                _build_query_plan_entry(
                    query=topic,
                    query_type="theme_fallback",
                    entities=[f"macro:{topic}"],
                    reason="Unmatched watch topic fallback",
                    source="fallback",
                    confidence="low",
                )
            )

    # Sort query plan by priority (lower number = higher priority)
    deduped_plan.sort(key=lambda x: (x.get("priority", 5), x.get("query_id", "")))

    # Convert entities to simple list of entity_ids for backward compatibility
    entity_ids = [e["entity_id"] for e in entities]

    return {
        "snapshot_type": "knowledge_graph_context",
        "generated_at": now,
        "portfolio_summary": {
            "holding_count": len(holdings),
            "total_value": round(total_value, 2),
        },
        "entities": entity_ids,
        "entities_detail": entities,  # New: detailed entity list
        "fund_entities": fund_entities,
        "watch_topics": list(WATCH_TOPICS),
        "query_plan": deduped_plan,
        "missing_data": missing_data,
        "data_quality": {
            "provider_snapshot_available": provider_snapshot is not None,
            "fund_profiles_available": len(fund_profiles) > 0,
            "fund_holdings_available": len(fund_holdings) > 0,
            "benchmark_available": any(benchmark_map.values()),
            "data_quality_flags": data_quality_flags,
        },
    }


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    """Read JSON file, return None if missing."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict] | None:
    """Read CSV file, return None if missing."""
    if not path.exists():
        return None
    rows: list[dict] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build knowledge graph context snapshot from portfolio data.")
    parser.add_argument(
        "--portfolio-input",
        required=True,
        type=Path,
        help="Path to portfolio_input.private.json (required)",
    )
    parser.add_argument(
        "--manual-transactions",
        type=Path,
        default=None,
        help="Path to manual_transactions.private.csv (optional)",
    )
    parser.add_argument(
        "--provider-snapshot",
        type=Path,
        default=None,
        help="Path to provider_data_snapshot.private.json (optional)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for knowledge_graph_context.private.json",
    )

    args = parser.parse_args(argv)

    # Read required input
    portfolio_input = _read_json(args.portfolio_input)
    if portfolio_input is None:
        print(f"ERROR: Required file not found: {args.portfolio_input}", file=sys.stderr)
        return 1

    # Read optional inputs
    manual_transactions = _read_csv(args.manual_transactions) if args.manual_transactions else None
    provider_snapshot = _read_json(args.provider_snapshot) if args.provider_snapshot else None

    # Build snapshot
    result = build_kg_context(
        portfolio_input=portfolio_input,
        manual_transactions=manual_transactions,
        provider_snapshot=provider_snapshot,
    )

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: knowledge graph context written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
