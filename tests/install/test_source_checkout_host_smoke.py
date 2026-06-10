"""Source-checkout smoke tests for external host runtime bridge usage."""

from __future__ import annotations

import json
from pathlib import Path

from tests.support.bridge_runner import parse_stdout_json, run_bridge_subprocess, write_temp_json


def _assert_json_skill_output(proc, *, skill_name: str, statuses: set[str]) -> dict:
    assert proc.returncode == 0, proc.stderr
    out = parse_stdout_json(proc)
    assert out["ok"] is True
    assert out["skill_name"] == skill_name
    assert out["status"] in statuses
    serialized = json.dumps(out).lower()
    for prohibited in (
        "plugin_invoked",
        "opencode_plugin_invoked",
        "python_invoked_by_opencode",
        "child_process",
        "subprocess_spawn",
    ):
        assert prohibited not in serialized, (
            f"output contains prohibited plugin-execution field: {prohibited}"
        )
    return out


def test_source_checkout_lists_skills() -> None:
    proc = run_bridge_subprocess(["--list-skills", "--pretty"])

    assert proc.returncode == 0, proc.stderr
    out = parse_stdout_json(proc)
    assert out["ok"] is True
    runtime_ids = {item["runtime_id"] for item in out["skills"]}
    assert {
        "fund_analysis",
        "decision_support",
        "thesis_generation",
        "news_research",
        "sentiment_analysis",
    } <= runtime_ids


def test_source_checkout_explains_fund_analysis_input() -> None:
    proc = run_bridge_subprocess(["--skill", "fund_analysis", "--explain-input", "--pretty"])

    assert proc.returncode == 0, proc.stderr
    out = parse_stdout_json(proc)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert "input_contract" in out


def test_source_checkout_validates_fake_fund_analysis_scenario() -> None:
    proc = run_bridge_subprocess([
        "--skill",
        "fund_analysis",
        "--input",
        "examples/scenarios/cn_fund_7d_redemption_fee.json",
        "--validate-input",
        "--pretty",
    ])

    assert proc.returncode == 0, proc.stderr
    out = parse_stdout_json(proc)
    assert out["ok"] is True
    assert out["validation_result"]["valid"] is True


def test_source_checkout_emits_markdown_report_from_fake_scenario() -> None:
    proc = run_bridge_subprocess([
        "--skill",
        "fund_analysis",
        "--input",
        "examples/scenarios/cn_fund_7d_redemption_fee.json",
        "--emit-report",
        "markdown",
    ])

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Personal fund report")
    assert "## Professional diagnostics" in proc.stdout
    assert "## Decision" not in proc.stdout
    assert "## ExecutionLedger" not in proc.stdout
    try:
        json.loads(proc.stdout)
        assert False, "markdown report output must not be JSON"
    except json.JSONDecodeError:
        pass


def test_source_checkout_runs_decision_support_fixture() -> None:
    proc = run_bridge_subprocess([
        "--skill",
        "decision_support",
        "--input",
        "examples/decision_support/single_active_buy_with_evidence.json",
        "--pretty",
    ])

    out = _assert_json_skill_output(proc, skill_name="decision_support", statuses={"OK"})
    assert "decision" in out["artifacts"]
    assert "execution_ledger" in out["artifacts"]


def test_source_checkout_runs_thesis_generation_fixture() -> None:
    proc = run_bridge_subprocess([
        "--skill",
        "thesis_generation",
        "--input",
        "examples/thesis_generation/evidence_graph_balanced_thesis.json",
        "--pretty",
    ])

    out = _assert_json_skill_output(
        proc,
        skill_name="thesis_generation",
        statuses={"OK", "PARTIAL"},
    )
    assert "thesis_draft" in out["artifacts"]
    assert "decision" not in out["artifacts"]
    assert "execution_ledger" not in out["artifacts"]


def test_source_checkout_runs_news_research_with_host_canned_mcp(tmp_path: Path) -> None:
    input_path = write_temp_json(
        tmp_path,
        {
            "payload": {"query": "fund:FAKE001"},
            "mcp_responses": {
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
            },
        },
        "news.json",
    )

    proc = run_bridge_subprocess([
        "--skill",
        "news_research",
        "--input",
        str(input_path),
        "--pretty",
    ])

    out = _assert_json_skill_output(proc, skill_name="news_research", statuses={"OK", "PARTIAL"})
    assert out["metadata"]["missing_mcp_capabilities"] == []
    assert set(out["used_mcp_capabilities"]) <= {"web_search", "financial_news"}
    assert out["artifacts"]["mcp_response"]


def test_source_checkout_runs_sentiment_analysis_with_host_canned_mcp(tmp_path: Path) -> None:
    input_path = write_temp_json(
        tmp_path,
        {
            "payload": {"query": "fund:FAKE001"},
            "mcp_responses": {
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
                }
            },
        },
        "sentiment.json",
    )

    proc = run_bridge_subprocess([
        "--skill",
        "sentiment_analysis",
        "--input",
        str(input_path),
        "--pretty",
    ])

    out = _assert_json_skill_output(
        proc,
        skill_name="sentiment_analysis",
        statuses={"OK", "PARTIAL"},
    )
    assert out["metadata"]["missing_mcp_capabilities"] == []
    assert out["used_mcp_capabilities"] == ["social_sentiment"]
    assert out["artifacts"]["mcp_response"]
