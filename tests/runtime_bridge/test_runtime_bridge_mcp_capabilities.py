"""Tests for the runtime bridge's MCP required-capability resolution.

The bridge must resolve required MCP capabilities from two sources:

1. The manifest ``skillpack/fund-agent.skillpack.yaml`` declares
   ``requires_mcp`` for each runtime skill (e.g. ``news_research``
   requires ``web_search`` and ``financial_news``).
2. The host's ``SkillInput.required_mcp_capabilities`` may add
   additional requirements.

The effective required set is the union of (1) and (2). The bridge
must build its ``InMemoryMCPHostAdapter`` over the effective set,
report missing capabilities honestly, and never silently drop a
manifest-required capability just because the host did not echo it
in the input.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json


ROOT = Path(__file__).resolve().parents[2]


def _run_inprocess(skill: str, payload: dict) -> dict:
    return run_bridge_inprocess_json(skill=skill, input_data=payload)


def test_news_research_without_mcp_responses_reports_missing_capabilities(
    tmp_path: Path,
) -> None:
    payload = {
        "payload": {"query": "fund:110011"},
    }
    out = _run_inprocess("news_research", payload)
    assert out["ok"] is False
    assert out["error"]["code"] == "MISSING_MCP_CAPABILITY"
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "web_search" in missing
    assert "financial_news" in missing
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "web_search" in required
    assert "financial_news" in required


def test_sentiment_analysis_without_mcp_responses_reports_missing_capability(
    tmp_path: Path,
) -> None:
    payload = {
        "payload": {"query": "fund:110011", "related_entities": ["110011"]},
    }
    out = _run_inprocess("sentiment_analysis", payload)
    assert out["ok"] is False
    assert out["error"]["code"] == "MISSING_MCP_CAPABILITY"
    missing = out["metadata"]["missing_mcp_capabilities"]
    assert "social_sentiment" in missing
    assert "social_sentiment" in out["metadata"]["required_mcp_capabilities"]


def test_news_research_with_canned_mcp_responses_runs(tmp_path: Path) -> None:
    payload = {
        "payload": {"query": "fund:110011"},
        "mcp_responses": {
            "web_search": {
                "items": [
                    {
                        "source_type": "news",
                        "timestamp": "2026-05-01T00:00:00",
                        "related_entities": ["110011"],
                        "claim": "Test news item",
                        "direction": "neutral",
                        "confidence_weight": 0.5,
                    }
                ]
            },
            "financial_news": {
                "items": [
                    {
                        "source_type": "financial_news",
                        "timestamp": "2026-05-02T00:00:00",
                        "related_entities": ["110011"],
                        "claim": "Earnings beat expectations",
                        "direction": "positive",
                        "confidence_weight": 0.7,
                    }
                ]
            },
        },
    }
    out = _run_inprocess("news_research", payload)
    assert out["ok"] is True
    assert out["metadata"]["missing_mcp_capabilities"] == []
    assert out["status"] in ("OK", "PARTIAL")
    assert out["skill_name"] == "news_research"


def test_convenience_input_respects_manifest_requires_mcp(tmp_path: Path) -> None:
    payload = {"payload": {"query": "fund:110011"}}
    out = _run_inprocess("news_research", payload)
    assert out["ok"] is False
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "web_search" in required
    assert "financial_news" in required
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "web_search" in missing
    assert "financial_news" in missing


def test_input_required_mcp_capabilities_adds_extra_requirements(tmp_path: Path) -> None:
    payload = {
        "payload": {"query": "fund:110011"},
        "required_mcp_capabilities": ["extra_capability"],
    }
    out = _run_inprocess("news_research", payload)
    assert out["ok"] is False
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "extra_capability" in required
    assert "web_search" in required
    assert "financial_news" in required
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "extra_capability" in missing


def test_skill_without_manifest_mcp_requirement_does_not_get_synthetic_missing(
    tmp_path: Path,
) -> None:
    payload = {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 100000,
                "cash_available": 10000,
                "positions": [],
            },
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
        },
    }
    out = _run_inprocess("fund_analysis", payload)
    assert out["ok"] is True
    assert out["metadata"]["required_mcp_capabilities"] == []
    assert out["metadata"]["missing_mcp_capabilities"] == []


def test_emit_envelope_falls_back_to_serialization_failed_envelope(tmp_path: Path) -> None:
    from src.skillpack import run_skill as bridge

    class Unserializable:
        def __str__(self) -> str:  # pragma: no cover - exercised by json.dumps
            raise TypeError("intentionally unserializable")

    out_path = tmp_path / "out.json"
    bad_envelope = {
        "ok": True,
        "skill_name": "fund_analysis",
        "metadata": {"bogus": Unserializable()},
    }
    rc = bridge._emit_envelope(bad_envelope, pretty=False, output_path=out_path)
    assert rc == 2, (
        f"expected exit code 2 when fallback fires, got {rc}"
    )
    text = out_path.read_text(encoding="utf-8")
    fallback = json.loads(text)
    assert fallback["ok"] is False
    assert fallback["error"]["code"] == "JSON_SERIALIZATION_FAILED"


def test_emit_envelope_serialization_failure_includes_no_traceback_on_stdout(
    tmp_path: Path, capsys,
) -> None:
    from src.skillpack import run_skill as bridge

    class Unserializable:
        def __str__(self) -> str:  # pragma: no cover - exercised by json.dumps
            raise TypeError("intentionally unserializable")

    bad_envelope = {
        "ok": True,
        "metadata": {"bogus": Unserializable()},
    }
    rc = bridge._emit_envelope(bad_envelope, pretty=False, output_path=None)
    assert rc == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out
    fallback = json.loads(captured.out)
    assert fallback["ok"] is False
    assert fallback["error"]["code"] == "JSON_SERIALIZATION_FAILED"
