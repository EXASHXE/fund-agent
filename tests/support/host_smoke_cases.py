"""Host smoke fixture registry for external-host runtime path testing.

Defines a small registry of deterministic smoke cases that prove an
external host can discover, validate, and run each skill through the
runtime bridge CLI.

All data is fake/sample only. No network calls, no provider SDKs,
no broker/order execution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostSmokeCase:
    skill: str
    slug: str
    input_path: str | None
    expected_statuses: tuple[str, ...]
    requires_mcp: tuple[str, ...] = ()
    mcp_responses: dict | None = None
    emit_report: str | None = None
    expected_artifacts: tuple[str, ...] = ()
    forbidden_artifacts: tuple[str, ...] = ()


CANNED_FINANCIAL_NEWS_MCP = {
    "web_search": {"items": []},
    "financial_news": {
        "items": [
            {
                "source_type": "financial_news",
                "timestamp": "2026-01-01T00:00:00",
                "related_entities": ["fund:FAKE001"],
                "claim": "Fake host-supplied financial news item",
                "direction": "neutral",
                "confidence_weight": 0.5,
            }
        ]
    },
}

CANNED_SOCIAL_SENTIMENT_MCP = {
    "social_sentiment": {
        "items": [
            {
                "source_type": "social_sentiment",
                "timestamp": "2026-01-01T00:00:00",
                "related_entities": ["fund:FAKE001"],
                "claim": "Fake host-supplied sentiment signal",
                "sentiment_score": 0.2,
                "direction": "neutral",
            }
        ]
    },
}

HOST_SMOKE_CASES: list[HostSmokeCase] = [
    HostSmokeCase(
        skill="fund_analysis",
        slug="fund-analysis",
        input_path="examples/scenarios/cn_fund_7d_redemption_fee.json",
        expected_statuses=("OK", "PARTIAL"),
        expected_artifacts=("report_sections",),
        forbidden_artifacts=("decision", "decisions", "execution_ledger", "execution_ledgers"),
    ),
    HostSmokeCase(
        skill="fund_analysis",
        slug="fund-analysis",
        input_path="examples/scenarios/cn_fund_7d_redemption_fee.json",
        expected_statuses=("OK", "PARTIAL"),
        emit_report="markdown",
        expected_artifacts=(),
        forbidden_artifacts=("decision", "decisions", "execution_ledger", "execution_ledgers"),
    ),
    HostSmokeCase(
        skill="decision_support",
        slug="decision-support",
        input_path="examples/decision_support/single_active_buy_with_evidence.json",
        expected_statuses=("OK",),
        expected_artifacts=("decision", "execution_ledger"),
        forbidden_artifacts=(),
    ),
    HostSmokeCase(
        skill="thesis_generation",
        slug="thesis-generation",
        input_path="examples/thesis_generation/evidence_graph_balanced_thesis.json",
        expected_statuses=("OK", "PARTIAL"),
        expected_artifacts=("thesis_draft",),
        forbidden_artifacts=("decision", "decisions", "execution_ledger", "execution_ledgers"),
    ),
    HostSmokeCase(
        skill="news_research",
        slug="news-research",
        input_path=None,
        expected_statuses=("OK", "PARTIAL"),
        requires_mcp=("web_search", "financial_news"),
        mcp_responses=CANNED_FINANCIAL_NEWS_MCP,
        expected_artifacts=("mcp_response",),
        forbidden_artifacts=(),
    ),
    HostSmokeCase(
        skill="sentiment_analysis",
        slug="sentiment-analysis",
        input_path=None,
        expected_statuses=("OK", "PARTIAL"),
        requires_mcp=("social_sentiment",),
        mcp_responses=CANNED_SOCIAL_SENTIMENT_MCP,
        expected_artifacts=("mcp_response",),
        forbidden_artifacts=(),
    ),
]
