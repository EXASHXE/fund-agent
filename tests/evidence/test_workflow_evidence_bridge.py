"""Tests for the workflow evidence bridge."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillOutput
from src.skills_runtime.workflow.evidence_bridge import (
    build_evidence_graph_from_workflow,
    convert_host_news_to_soft_evidence,
    convert_host_sentiment_to_soft_evidence,
    convert_host_benchmark_to_hard_evidence,
    convert_host_fee_to_hard_evidence,
    convert_host_redemption_to_hard_evidence,
    resolve_evidence_source_refs,
    WorkflowEvidenceGraphResult,
    _stable_evidence_id,
    _stable_timestamp,
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


# ── A. Benchmark / Fee / Redemption converters ──────────────────────────────


class TestBenchmarkConverter:
    def test_converts_benchmark_dict_item(self):
        item = convert_host_benchmark_to_hard_evidence({
            "fund_code": "008253",
            "nav": 6400.0,
            "date": "2026-06-01",
        })
        assert item is not None
        assert item.evidence_type == "HardEvidence"
        assert item.source_type == "benchmark_history"
        assert item.confidence_weight == 1.0
        assert "008253" in item.related_entities

    def test_converts_benchmark_with_source(self):
        item = convert_host_benchmark_to_hard_evidence({
            "fund_code": "008253",
            "source": "custom_benchmark",
        })
        assert item.source_type == "custom_benchmark"

    def test_benchmark_without_fund_code_uses_entities_field(self):
        item = convert_host_benchmark_to_hard_evidence({
            "entities": ["001198"],
        })
        assert item is not None
        assert item.related_entities == ["001198"]

    def test_benchmark_not_dict(self):
        assert convert_host_benchmark_to_hard_evidence(None) is None
        assert convert_host_benchmark_to_hard_evidence("bad") is None


class TestFeeConverter:
    def test_converts_fee_dict_item(self):
        item = convert_host_fee_to_hard_evidence({
            "fund_code": "008253",
            "management_fee": 0.005,
            "redemption_fee_pct": 0.005,
        })
        assert item is not None
        assert item.evidence_type == "HardEvidence"
        assert item.source_type == "fee_schedule"
        assert item.confidence_weight == 1.0

    def test_fee_not_dict(self):
        assert convert_host_fee_to_hard_evidence(None) is None


class TestRedemptionConverter:
    def test_converts_redemption_dict_item(self):
        item = convert_host_redemption_to_hard_evidence({
            "fund_code": "008253",
            "holding_period_days": 7,
            "short_redemption_fee_pct": 0.015,
        })
        assert item is not None
        assert item.evidence_type == "HardEvidence"
        assert item.source_type == "redemption_rules"
        assert item.confidence_weight == 1.0

    def test_redemption_not_dict(self):
        assert convert_host_redemption_to_hard_evidence(None) is None


class TestBridgeIngestsHardEvidence:
    """Bridge ingests benchmark, fee, and redemption evidence."""
    
    def _make_fa_output(self):
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
            "evidence_items": [ei.to_dict()],
            "artifacts": {},
            "status": "OK",
            "portfolio": {"as_of_date": "2026-06-01"},
        }

    def test_ingests_benchmark_list(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_benchmark_evidence=[
                {"fund_code": "008253"},
                {"fund_code": "001198"},
            ],
        )
        hard = result.graph.hard_evidence_count()
        assert hard >= 3  # fa hard + 2 benchmark

    def test_ingests_benchmark_dict_keyed_by_fund_code(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_benchmark_evidence={
                "008253": {"nav": 6400.0},
                "001198": {"nav": 4500.0},
            },
        )
        hard = result.graph.hard_evidence_count()
        assert hard >= 3

    def test_ingests_fee_evidence(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_fee_evidence=[
                {"fund_code": "008253", "management_fee": 0.005},
            ],
        )
        hard = result.graph.hard_evidence_count()
        assert hard >= 2

    def test_ingests_redemption_evidence(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_redemption_evidence=[
                {"fund_code": "008253", "short_redemption_fee_pct": 0.015},
            ],
        )
        hard = result.graph.hard_evidence_count()
        assert hard >= 2

    def test_ingests_fee_dict_keyed_by_fund_code(self):
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=self._make_fa_output(),
            host_fee_evidence={
                "008253": {"management_fee": 0.005},
            },
        )
        hard = result.graph.hard_evidence_count()
        assert hard >= 2


# ── B. Determinism tests ────────────────────────────────────────────────────


class TestDeterministicEvidenceIDs:
    """Evidence IDs and timestamps are stable and deterministic."""

    def test_stable_evidence_id_same_input_same_output(self):
        payload = {"source_type": "test", "entities": ["008253"], "claim": "test claim"}
        id1 = _stable_evidence_id("pref", payload)
        id2 = _stable_evidence_id("pref", payload)
        assert id1 == id2

    def test_stable_evidence_id_different_input_different_output(self):
        id1 = _stable_evidence_id("pref", {"source_type": "test", "entities": ["A"], "claim": "X"})
        id2 = _stable_evidence_id("pref", {"source_type": "test", "entities": ["B"], "claim": "Y"})
        assert id1 != id2

    def test_stable_timestamp_from_item_date(self):
        ts = _stable_timestamp({"date": "2026-06-01"}, None)
        assert ts.year == 2026
        assert ts.month == 6

    def test_stable_timestamp_fallback_as_of_date(self):
        ts = _stable_timestamp({}, "2026-01-15")
        assert ts.year == 2026
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 0

    def test_stable_timestamp_frozen_default(self):
        ts = _stable_timestamp({}, None)
        assert ts.year == 1970
        assert ts.month == 1

    def test_news_converter_produces_stable_id(self):
        item1 = convert_host_news_to_soft_evidence({
            "title": "Same news", "entities": ["008253"], "source": "finnhub",
        })
        item2 = convert_host_news_to_soft_evidence({
            "title": "Same news", "entities": ["008253"], "source": "finnhub",
        })
        assert item1.evidence_id == item2.evidence_id

    def test_sentiment_converter_produces_stable_id(self):
        item1 = convert_host_sentiment_to_soft_evidence({
            "entity": "008253", "score": 0.5, "source": "reddit",
        })
        item2 = convert_host_sentiment_to_soft_evidence({
            "entity": "008253", "score": 0.5, "source": "reddit",
        })
        assert item1.evidence_id == item2.evidence_id

    def test_diagnostic_evidence_stable_ids(self):
        fa_output = {
            "evidence_items": [],
            "artifacts": {
                "redemption_fee_risk": {
                    "fund_codes": ["008253"],
                    "summary": {"has_blocker": True, "fund_codes": ["008253"]},
                },
            },
            "status": "OK",
        }
        result1 = build_evidence_graph_from_workflow(fund_analysis_output=fa_output)
        result2 = build_evidence_graph_from_workflow(fund_analysis_output=fa_output)
        items1 = dict(result1.graph.items)
        items2 = dict(result2.graph.items)
        assert items1.keys() == items2.keys()
        for key in items1:
            assert items1[key].evidence_id == items2[key].evidence_id

    def test_bridge_no_uuid_import_in_source(self):
        import inspect
        from src.skills_runtime.workflow import evidence_bridge as mod
        source = inspect.getsource(mod)
        assert "uuid" not in source, "evidence_bridge should not import uuid"
        assert "datetime.now" not in source and "datetime.now(" not in source, \
            "evidence_bridge should not use datetime.now"


# ── C. Evidence source refs resolver ────────────────────────────────────────


class TestEvidenceSourceRefsResolver:
    """resolve_evidence_source_refs maps aliases to real graph evidence IDs."""

    def test_resolves_known_source_refs(self):
        graph = EvidenceGraph()
        ei = EvidenceItem(
            evidence_id="bm-ev-001",
            evidence_type="HardEvidence",
            source_type="benchmark_history",
            timestamp=datetime.now(timezone.utc),
            related_entities=["001198"],
            claim="Benchmark data",
            value={},
            confidence_weight=1.0,
        )
        graph.add(ei)

        trade_plan = {
            "suggested_trade_plan": [{
                "trade_id": "t1",
                "action": "INCREASE",
                "evidence_source_refs": ["benchmark_history"],
                "evidence_refs": [],
            }]
        }
        resolved, warnings = resolve_evidence_source_refs(trade_plan, graph)
        assert len(warnings) == 0
        t1 = resolved["suggested_trade_plan"][0]
        assert len(t1["evidence_refs"]) == 1
        assert t1["evidence_refs"][0] == "bm-ev-001"

    def test_unresolved_source_ref_warns(self):
        graph = EvidenceGraph()
        trade_plan = {
            "suggested_trade_plan": [{
                "trade_id": "t1",
                "action": "INCREASE",
                "evidence_source_refs": ["nonexistent_ref"],
                "evidence_refs": [],
            }]
        }
        resolved, warnings = resolve_evidence_source_refs(trade_plan, graph)
        assert len(warnings) >= 1
        t1 = resolved["suggested_trade_plan"][0]
        assert len(t1["evidence_refs"]) == 0

    def test_no_source_refs_no_change(self):
        graph = EvidenceGraph()
        trade_plan = {
            "suggested_trade_plan": [{
                "trade_id": "t1",
                "action": "HOLD",
                "evidence_refs": ["existing-ref"],
            }]
        }
        resolved, warnings = resolve_evidence_source_refs(trade_plan, graph)
        assert len(warnings) == 0
        t1 = resolved["suggested_trade_plan"][0]
        assert t1["evidence_refs"] == ["existing-ref"]

    def test_does_not_assign_arbitrary_ids(self):
        graph = EvidenceGraph()
        ei = EvidenceItem(
            evidence_id="some-id",
            evidence_type="HardEvidence",
            source_type="irrelevant",
            timestamp=datetime.now(timezone.utc),
            related_entities=["TEST"],
            claim="Irrelevant",
            value={},
            confidence_weight=1.0,
        )
        graph.add(ei)
        trade_plan = {
            "suggested_trade_plan": [{
                "trade_id": "t1",
                "action": "INCREASE",
                "evidence_source_refs": [],  # empty source refs
                "evidence_refs": [],         # empty evidence refs
            }]
        }
        resolved, warnings = resolve_evidence_source_refs(trade_plan, graph)
        t1 = resolved["suggested_trade_plan"][0]
        assert len(t1["evidence_refs"]) == 0, "Should not assign arbitrary IDs"

