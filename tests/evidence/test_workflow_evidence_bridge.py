"""Tests for the workflow evidence bridge."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillOutput
from src.tools.workflow.evidence_bridge import (
    build_evidence_graph_from_workflow,
    convert_host_news_to_soft_evidence,
    convert_host_sentiment_to_soft_evidence,
    WorkflowEvidenceGraphResult,
)


class TestConvertNewsToSoftEvidence:
    """Host news → SoftEvidence conversion."""

    def test_valid_news_item_converts(self):
        item = convert_host_news_to_soft_evidence({
            "title": "半导体行业景气度维持高位",
            "entities": ["008253"],
            "direction": "positive",
            "confidence": 0.75,
            "source": "finnhub",
        })
        assert item is not None
        assert item.evidence_type == "SoftEvidence"
        assert item.claim == "半导体行业景气度维持高位"
        assert item.related_entities == ["008253"]
        assert item.direction == "positive"
        assert 0.1 <= item.confidence_weight <= 0.9

    def test_news_item_without_title_returns_none(self):
        item = convert_host_news_to_soft_evidence({
            "entities": ["008253"],
        })
        assert item is None

    def test_news_item_without_entities_returns_none(self):
        item = convert_host_news_to_soft_evidence({
            "title": "Some news",
        })
        assert item is None

    def test_news_item_not_dict_returns_none(self):
        assert convert_host_news_to_soft_evidence("not a dict") is None
        assert convert_host_news_to_soft_evidence(None) is None
        assert convert_host_news_to_soft_evidence(42) is None

    def test_news_item_single_entity_string(self):
        item = convert_host_news_to_soft_evidence({
            "title": "News",
            "entities": "008253",
        })
        assert item is not None
        assert item.related_entities == ["008253"]

    def test_news_item_confidence_clamped(self):
        item = convert_host_news_to_soft_evidence({
            "title": "News",
            "entities": ["008253"],
            "confidence": 2.0,
        })
        assert item.confidence_weight == 0.9

        item2 = convert_host_news_to_soft_evidence({
            "title": "News",
            "entities": ["008253"],
            "confidence": -1.0,
        })
        assert item2.confidence_weight == 0.1

    def test_news_item_alternative_keys(self):
        item = convert_host_news_to_soft_evidence({
            "claim": "Alternative claim key",
            "related_entities": ["008253"],
            "confidence_weight": 0.6,
        })
        assert item is not None
        assert item.claim == "Alternative claim key"


class TestConvertSentimentToSoftEvidence:
    """Host sentiment → SoftEvidence conversion."""

    def test_valid_sentiment_item_converts(self):
        item = convert_host_sentiment_to_soft_evidence({
            "entity": "008253",
            "score": 0.65,
            "confidence": 0.70,
            "source": "reddit",
            "claim": "Positive sentiment",
        })
        assert item is not None
        assert item.evidence_type == "SoftEvidence"
        assert item.direction == "positive"
        assert item.related_entities == ["008253"]

    def test_negative_sentiment_direction(self):
        item = convert_host_sentiment_to_soft_evidence({
            "entity": "008253",
            "score": -0.5,
        })
        assert item.direction == "negative"

    def test_neutral_sentiment_direction(self):
        item = convert_host_sentiment_to_soft_evidence({
            "entity": "008253",
            "score": 0.0,
        })
        assert item.direction == "neutral"

    def test_sentiment_without_entity_returns_none(self):
        item = convert_host_sentiment_to_soft_evidence({
            "score": 0.5,
        })
        assert item is None

    def test_sentiment_with_entities_list(self):
        item = convert_host_sentiment_to_soft_evidence({
            "entities": ["008253", "001198"],
            "score": 0.3,
        })
        assert item is not None
        assert item.related_entities == ["008253", "001198"]

    def test_sentiment_not_dict_returns_none(self):
        assert convert_host_sentiment_to_soft_evidence(None) is None
        assert convert_host_sentiment_to_soft_evidence("bad") is None


class TestBuildEvidenceGraphFromWorkflow:
    """End-to-end bridge: fund_analysis + host evidence → EvidenceGraph."""

    def _make_fa_output(self) -> dict[str, Any]:
        ei = EvidenceItem(
            evidence_id="hard-001",
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(timezone.utc),
            related_entities=["008253"],
            claim="Position weight: 30%",
            value={"weight": 0.30},
            confidence_weight=1.0,
            direction="neutral",
        )
        return {
            "step_id": "fa-step",
            "skill_name": "fund_analysis",
            "evidence_items": [ei.to_dict()],
            "artifacts": {
                "portfolio_summary": {"total_value": 300000, "position_count": 3},
                "profit_protection_diagnostics": {
                    "fund_codes": ["008253"],
                    "items": [{"fund_code": "008253", "profit_level": "high"}],
                    "summary": {"fund_codes": ["008253"]},
                },
                "evidence_gap_diagnostics": {
                    "missing_recent_news": False,
                    "missing_sentiment": False,
                },
            },
            "status": "OK",
            "errors": [],
            "warnings": [],
        }

    def test_build_graph_from_fund_analysis_only(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
        )
        assert result.included_evidence_count >= 1
        assert isinstance(result.graph, EvidenceGraph)
        assert result.graph.hard_evidence_count() >= 1
        assert result.host_soft_evidence_count == 0

    def test_build_graph_with_host_news(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_news_evidence=[
                {"title": "News 1", "entities": ["008253"], "direction": "positive"},
                {"title": "News 2", "entities": ["001198"], "direction": "negative"},
            ],
        )
        assert result.host_soft_evidence_count >= 2
        assert result.graph.soft_evidence_count() >= 2

    def test_build_graph_with_host_sentiment(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_sentiment_evidence=[
                {"entity": "008253", "score": 0.5},
                {"entity": "001198", "score": -0.3},
            ],
        )
        assert result.host_soft_evidence_count >= 2

    def test_invalid_host_evidence_warned(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_news_evidence=[{"no_title": True}],
            host_sentiment_evidence=[{"no_entity": True}],
        )
        missing = result.missing_or_invalid_evidence
        assert len(missing) > 0 or len(result.warnings) > 0

    def test_missing_news_produces_warning(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_news_evidence=[],
        )
        warnings = result.warnings
        assert any("news" in w.lower() for w in warnings), (
            f"Expected warning about missing news, got {warnings}"
        )

    def test_result_to_dict(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
        )
        d = result.to_dict()
        assert "graph" in d
        assert "included_evidence_count" in d
        assert "host_soft_evidence_count" in d
        assert isinstance(d["graph"], dict)
        assert "items" in d["graph"]

    def test_no_execution_fields(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
        )
        d = result.to_dict()

        def _check_no_exec(data, path=""):
            import json
            forbidden = {"broker_order_id", "order_id", "order_status",
                         "filled_quantity", "fill_price", "execution_venue",
                         "submitted_at", "broker", "exchange_order_id"}
            if isinstance(data, dict):
                for k in data:
                    assert k not in forbidden, f"Forbidden field '{k}' at {path}"
                    _check_no_exec(data[k], f"{path}.{k}")
            elif isinstance(data, list):
                for i, v in enumerate(data):
                    _check_no_exec(v, f"{path}[{i}]")

        _check_no_exec(d)

    def test_empty_fund_analysis_handled(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=None,
        )
        assert result.included_evidence_count == 0
        assert result.graph is not None

    def test_bridge_preserves_evidence_id_stability(self):
        from datetime import timezone

        ei1 = EvidenceItem(
            evidence_id="stable-001",
            evidence_type="HardEvidence",
            source_type="test",
            timestamp=datetime.now(timezone.utc),
            related_entities=["TEST"],
            claim="Stable evidence",
            value={"v": 1},
            confidence_weight=1.0,
        )
        fa_output = {
            "evidence_items": [ei1.to_dict()],
            "artifacts": {},
            "status": "OK",
        }
        result = build_evidence_graph_from_workflow(fund_analysis_output=fa_output)
        assert "stable-001" in result.graph.items
        item = result.graph.items["stable-001"]
        assert item.claim == "Stable evidence"

    def test_bridge_graph_to_dict_accepted_by_decision_support(self):
        """The graph from the bridge should serialize and be accepted."""
        ei = EvidenceItem(
            evidence_id="accept-test-001",
            evidence_type="SoftEvidence",
            source_type="test_news",
            timestamp=datetime.now(timezone.utc),
            related_entities=["008253"],
            claim="Test evidence",
            value={"test": True},
            confidence_weight=0.7,
            direction="positive",
        )
        fa_output = {
            "evidence_items": [ei.to_dict()],
            "artifacts": {
                "evidence_gap_diagnostics": {
                    "missing_recent_news": False,
                    "missing_sentiment": False,
                    "missing_transaction_history": False,
                },
                "analysis_plan": {"blockers": [], "decision_support_ready": True},
            },
            "status": "OK",
        }
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=fa_output,
            host_news_evidence=[
                {"title": "Positive news", "entities": ["008253"], "direction": "positive", "confidence": 0.7},
            ],
        )
        graph_dict = result.graph.to_dict()
        assert "items" in graph_dict
        assert "edges" in graph_dict
        assert "stats" in graph_dict
        assert graph_dict["stats"]["total"] >= 2
