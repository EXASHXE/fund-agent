"""Normalize fake MCP responses into fund_analysis-compatible payload fields.

Dev-only. Core runtime must not import this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAKE_RESPONSES_PATH = Path(__file__).parent / "fake_mcp_responses.json"


def load_fake_responses() -> dict[str, Any]:
    with open(FAKE_RESPONSES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_news_evidence(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw:
        return []
    first = raw[0]
    if "source_type" in first:
        return [
            {
                "source": item.get("source_type", ""),
                "headline": item.get("claim", ""),
                "date": item.get("timestamp", ""),
                "sentiment": item.get("direction", "neutral"),
            }
            for item in raw
        ]
    return [
        {
            "source": item.get("source", ""),
            "headline": item.get("headline", item.get("title", "")),
            "date": item.get("date", ""),
            "sentiment": item.get("sentiment", "neutral"),
        }
        for item in raw
    ]


def normalize_sentiment_evidence(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw:
        return []
    first = raw[0]
    if "source_type" in first:
        return [
            {
                "fund_code": next(
                    (e.split(":")[1] for e in item.get("related_entities", []) if e.startswith("fund:")),
                    "",
                ),
                "sentiment": item.get("direction", "neutral"),
                "score": item.get("confidence_weight", 0.5),
            }
            for item in raw
        ]
    return [
        {
            "fund_code": item.get("fund_code", ""),
            "sentiment": item.get("sentiment", "neutral"),
            "score": item.get("score", 0.5),
        }
        for item in raw
    ]


def normalize_benchmark_history(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def normalize_web_search(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw:
        return []
    return [
        {
            "source": "web_search",
            "headline": item.get("title", item.get("snippet", "")),
            "date": item.get("date", ""),
            "sentiment": "neutral",
        }
        for item in raw
    ]


def normalize_fund_metadata_lookup(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def normalize_fund_fee_schedule(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def normalize_all(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw is None:
        raw = load_fake_responses()

    if "news_evidence" in raw:
        news_normalized = normalize_news_evidence(raw["news_evidence"])
    elif "financial_news" in raw:
        news_normalized = normalize_news_evidence(raw["financial_news"])
    elif "web_search" in raw:
        news_normalized = normalize_web_search(raw["web_search"])
    else:
        news_normalized = []

    if "sentiment_evidence" in raw:
        sentiment_normalized = normalize_sentiment_evidence(raw["sentiment_evidence"])
    elif "social_sentiment" in raw:
        sentiment_normalized = normalize_sentiment_evidence(raw["social_sentiment"])
    else:
        sentiment_normalized = []

    benchmark_raw = raw.get("benchmark_history") or raw.get("benchmark_price_history") or {}
    fund_profiles_raw = raw.get("fund_profiles") or raw.get("fund_metadata_lookup") or {}
    fee_schedules_raw = raw.get("fee_schedules") or raw.get("fund_fee_schedule") or {}
    redemption_rules_raw = raw.get("redemption_rules") or {}

    return {
        "news_evidence": news_normalized,
        "sentiment_evidence": sentiment_normalized,
        "benchmark_history": normalize_benchmark_history(benchmark_raw),
        "fund_profiles": fund_profiles_raw,
        "fee_schedules": fee_schedules_raw,
        "redemption_rules": redemption_rules_raw,
    }


if __name__ == "__main__":
    result = normalize_all()
    print(json.dumps(result, indent=2, ensure_ascii=False))
