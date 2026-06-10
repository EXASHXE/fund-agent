#!/usr/bin/env python3
"""Source-checkout host smoke script.

Simulates what a generic external host would do after checking out
the repository. Runs deterministic, local-only checks using fake/sample
data only. No network calls, no provider SDKs, no broker/order execution.

Exit 0 on success, non-zero on failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = [sys.executable, str(ROOT / "scripts" / "run_skill.py")]
ENV_PYTHONPATH = str(ROOT)

SKILLS = ["fund_analysis", "decision_support", "thesis_generation", "news_research", "sentiment_analysis"]
SLUGS = ["fund-analysis", "decision-support", "thesis-generation", "news-research", "sentiment-analysis"]

CANNED_NEWS_MCP = {
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

CANNED_SENTIMENT_MCP = {
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

checks_passed = 0
checks_failed = 0


def _run(args: list[str], *, expect_rc_zero: bool = True) -> dict | str:
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = ENV_PYTHONPATH
    result = subprocess.run(
        BRIDGE + args,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=60,
    )
    if expect_rc_zero and result.returncode != 0:
        raise RuntimeError(f"Bridge failed: rc={result.returncode} stderr={result.stderr[:200]}")
    stdout = result.stdout.strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return stdout


def _check(label: str, fn) -> None:
    global checks_passed, checks_failed
    try:
        fn()
        checks_passed += 1
        print(f"  PASS  {label}")
    except Exception as exc:
        checks_failed += 1
        print(f"  FAIL  {label}: {exc}")


def main() -> int:
    print("=== fund-agent host smoke ===")
    print()

    def check_list_skills():
        data = _run(["--list-skills", "--pretty"])
        assert data.get("ok") is True
        ids = {s["runtime_id"] for s in data["skills"]}
        assert set(SKILLS) <= ids
    _check("list-skills", check_list_skills)

    for skill in SKILLS:
        def _make_explain(s=skill):
            def check():
                data = _run(["--skill", s, "--explain-input", "--pretty"])
                assert data.get("ok") is True
                assert data.get("skill_name") == s
            return check
        _check(f"explain-input {skill}", _make_explain())

    for skill in SKILLS:
        def _make_schema(s=skill):
            def check():
                data = _run(["--skill", s, "--output-schema", "--pretty"])
                assert data.get("ok") is True
            return check
        _check(f"output-schema {skill}", _make_schema())

    def check_validate_fund_analysis():
        data = _run([
            "--skill", "fund_analysis",
            "--input", "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "--validate-input", "--pretty",
        ])
        assert data.get("ok") is True
        assert data["validation_result"]["valid"] is True
    _check("validate fund_analysis fixture", check_validate_fund_analysis)

    def check_run_fund_analysis():
        data = _run([
            "--skill", "fund_analysis",
            "--input", "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "--pretty",
        ])
        assert data.get("skill_name") == "fund_analysis"
        assert data.get("status") in {"OK", "PARTIAL"}
        artifacts = data.get("artifacts", {})
        assert "report_sections" in artifacts
        assert "decision" not in artifacts
    _check("run fund_analysis JSON", check_run_fund_analysis)

    def check_run_fund_analysis_markdown():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            out_path = f.name
        _run([
            "--skill", "fund_analysis",
            "--input", "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "--emit-report", "markdown",
            "--output", out_path,
        ])
        text = Path(out_path).read_text(encoding="utf-8")
        assert text.startswith("# Personal fund report")
        assert "## Executive summary" in text
    _check("run fund_analysis Markdown", check_run_fund_analysis_markdown)

    def check_run_decision_support():
        data = _run([
            "--skill", "decision_support",
            "--input", "examples/decision_support/single_active_buy_with_evidence.json",
            "--pretty",
        ])
        assert data.get("skill_name") == "decision_support"
        assert data.get("status") in {"OK", "PARTIAL"}
        artifacts = data.get("artifacts", {})
        assert "decision" in artifacts
        assert "execution_ledger" in artifacts
    _check("run decision_support", check_run_decision_support)

    def check_run_thesis_generation():
        data = _run([
            "--skill", "thesis_generation",
            "--input", "examples/thesis_generation/evidence_graph_balanced_thesis.json",
            "--pretty",
        ])
        assert data.get("skill_name") == "thesis_generation"
        assert data.get("status") in {"OK", "PARTIAL"}
        artifacts = data.get("artifacts", {})
        assert "thesis_draft" in artifacts
        assert "decision" not in artifacts
    _check("run thesis_generation", check_run_thesis_generation)

    def check_run_news_research_canned():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"payload": {"query": "fund:FAKE001"}, "mcp_responses": CANNED_NEWS_MCP}, f)
            input_path = f.name
        data = _run(["--skill", "news_research", "--input", input_path, "--pretty"])
        assert data.get("skill_name") == "news_research"
        assert data.get("status") in {"OK", "PARTIAL"}
    _check("run news_research with canned MCP", check_run_news_research_canned)

    def check_run_sentiment_analysis_canned():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"payload": {"query": "fund:FAKE001"}, "mcp_responses": CANNED_SENTIMENT_MCP}, f)
            input_path = f.name
        data = _run(["--skill", "sentiment_analysis", "--input", input_path, "--pretty"])
        assert data.get("skill_name") == "sentiment_analysis"
        assert data.get("status") in {"OK", "PARTIAL"}
    _check("run sentiment_analysis with canned MCP", check_run_sentiment_analysis_canned)

    print()
    if checks_failed:
        print(f"FAILED: {checks_failed} check(s) failed, {checks_passed} passed")
        return 1
    print(f"All {checks_passed} host smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
