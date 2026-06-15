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
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
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
# Core builder
# ---------------------------------------------------------------------------


def build_kg_context(
    portfolio_input: dict,
    manual_transactions: list[dict] | None = None,
    provider_snapshot: dict | None = None,
) -> dict:
    """Build the knowledge graph context snapshot dict."""
    now = datetime.now(timezone.utc).isoformat()

    holdings = portfolio_input.get("holdings", portfolio_input.get("positions", []))
    if not isinstance(holdings, list):
        holdings = []

    # Portfolio summary
    total_value = 0.0
    for h in holdings:
        try:
            total_value += float(h.get("current_value", 0))
        except (TypeError, ValueError):
            pass

    entities: list[str] = []
    fund_entities: list[dict] = []
    query_plan: list[dict] = []
    missing_data: dict = {
        "fund_code_missing": [],
        "units_missing": [],
        "nav_missing": [],
        "cost_basis_missing": [],
        "provider_snapshot_missing": provider_snapshot is None,
        "manual_transactions_missing": manual_transactions is None,
    }

    seen_entities: set[str] = set()

    for idx, h in enumerate(holdings):
        if not isinstance(h, dict):
            continue

        fund_name = str(h.get("fund_name", h.get("name", "")))
        fund_code = h.get("fund_code", h.get("code", ""))
        if fund_code:
            fund_code = str(fund_code)
        else:
            fund_code = ""
        sector = str(h.get("sector", h.get("industry", "")))
        theme = h.get("theme", "")

        # Extract theme_tags
        theme_tags: list[str] = []
        if isinstance(theme, str) and theme:
            theme_tags = [t.strip() for t in theme.split(",") if t.strip()]
        elif isinstance(theme, list):
            theme_tags = [str(t).strip() for t in theme if t]

        # Match watch topics
        matched_topics = _match_topics(fund_name, fund_code, sector)
        # Add theme-derived topics
        for tag in theme_tags:
            for topic in WATCH_TOPICS:
                if tag in topic or topic in tag:
                    if topic not in matched_topics:
                        matched_topics.append(topic)

        # Infer risk bucket
        risk_bucket = h.get("risk_bucket", "") or _infer_risk_bucket(fund_name, sector, matched_topics)

        # Build entities
        if fund_code:
            ent = f"fund:{fund_code}"
            if ent not in seen_entities:
                entities.append(ent)
                seen_entities.add(ent)
        if fund_name:
            ent = f"fund_name:{fund_name}"
            if ent not in seen_entities:
                entities.append(ent)
                seen_entities.add(ent)
        if sector:
            ent = f"sector:{sector}"
            if ent not in seen_entities:
                entities.append(ent)
                seen_entities.add(ent)
        for topic in matched_topics:
            ent = f"macro:{topic}"
            if ent not in seen_entities:
                entities.append(ent)
                seen_entities.add(ent)
        if risk_bucket and risk_bucket != "unknown":
            ent = f"risk_bucket:{risk_bucket}"
            if ent not in seen_entities:
                entities.append(ent)
                seen_entities.add(ent)

        # Fund entity record
        fund_ent = {
            "fund_code": fund_code or "",
            "fund_name": fund_name,
            "sector": sector,
            "theme_tags": matched_topics,
            "risk_bucket": risk_bucket,
        }
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
        if h.get("nav") is None:
            if "nav" in h:
                missing_data["nav_missing"].append(fund_code or fund_name or f"holding_{idx}")
        if h.get("cost_basis") is None and h.get("total_cost") is None:
            if "cost_basis" in h or "total_cost" in h:
                missing_data["cost_basis_missing"].append(fund_code or fund_name or f"holding_{idx}")

        # Build query plan entries
        query_id_base = fund_code or fund_name or f"holding_{idx}"
        if fund_name:
            qid = _stable_hash(f"q_{query_id_base}_name")
            query_plan.append(
                {
                    "query_id": qid,
                    "query": fund_name,
                    "entities": [f"fund_name:{fund_name}"] + ([f"fund:{fund_code}"] if fund_code else []),
                    "topic_tags": matched_topics,
                }
            )
        if fund_code:
            qid = _stable_hash(f"q_{query_id_base}_code")
            query_plan.append(
                {
                    "query_id": qid,
                    "query": fund_code,
                    "entities": [f"fund:{fund_code}"],
                    "topic_tags": matched_topics,
                }
            )
        if sector:
            qid = _stable_hash(f"q_{query_id_base}_sector")
            query_plan.append(
                {
                    "query_id": qid,
                    "query": sector,
                    "entities": [f"sector:{sector}"],
                    "topic_tags": matched_topics,
                }
            )
        for topic in matched_topics:
            qid = _stable_hash(f"q_{query_id_base}_topic_{topic}")
            query_plan.append(
                {
                    "query_id": qid,
                    "query": topic,
                    "entities": [f"macro:{topic}"],
                    "topic_tags": [topic],
                }
            )

    # Deduplicate query plan by query_id
    seen_qids: set[str] = set()
    deduped_plan: list[dict] = []
    for q in query_plan:
        if q["query_id"] not in seen_qids:
            deduped_plan.append(q)
            seen_qids.add(q["query_id"])

    # Add macro-level queries for unmatched watch topics
    matched_topic_set: set[str] = set()
    for fe in fund_entities:
        for t in fe["theme_tags"]:
            matched_topic_set.add(t)

    for topic in WATCH_TOPICS:
        if topic not in matched_topic_set:
            qid = _stable_hash(f"q_macro_unmatched_{topic}")
            deduped_plan.append(
                {
                    "query_id": qid,
                    "query": topic,
                    "entities": [f"macro:{topic}"],
                    "topic_tags": [topic],
                }
            )

    return {
        "snapshot_type": "knowledge_graph_context",
        "generated_at": now,
        "portfolio_summary": {
            "holding_count": len(holdings),
            "total_value": round(total_value, 2),
        },
        "entities": entities,
        "fund_entities": fund_entities,
        "watch_topics": list(WATCH_TOPICS),
        "query_plan": deduped_plan,
        "missing_data": missing_data,
    }


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    """Read JSON file, return None if missing."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict] | None:
    """Read CSV file, return None if missing."""
    if not path.exists():
        return None
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
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
