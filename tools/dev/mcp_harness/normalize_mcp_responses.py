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
    return [
        {
            "source": item.get("source_type", ""),
            "headline": item.get("claim", ""),
            "date": item.get("timestamp", ""),
            "sentiment": item.get("direction", "neutral"),
        }
        for item in raw
    ]


def normalize_sentiment_evidence(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def normalize_benchmark_history(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def normalize_all(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw is None:
        raw = load_fake_responses()
    return {
        "news_evidence": normalize_news_evidence(raw.get("news_evidence", [])),
        "sentiment_evidence": normalize_sentiment_evidence(raw.get("sentiment_evidence", [])),
        "benchmark_history": normalize_benchmark_history(raw.get("benchmark_history", {})),
        "fund_profiles": raw.get("fund_profiles", {}),
        "fee_schedules": raw.get("fee_schedules", {}),
        "redemption_rules": raw.get("redemption_rules", {}),
    }


if __name__ == "__main__":
    result = normalize_all()
    print(json.dumps(result, indent=2, ensure_ascii=False))
