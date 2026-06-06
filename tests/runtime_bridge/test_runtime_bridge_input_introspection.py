"""Runtime bridge input introspection command tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _json(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip(), f"stdout must contain JSON, stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


def test_explain_input_fund_analysis_returns_contract_without_input() -> None:
    proc = _run(["--skill", "fund_analysis", "--explain-input", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["doc_slug"] == "fund-analysis"
    assert out["command"] == "explain-input"

    contract = out["input_contract"]
    shape_names = {item["name"] for item in contract["accepted_envelope_shapes"]}
    assert {"full_skill_input", "payload_only"} <= shape_names

    modes = {item["mode"] for item in contract["minimum_required"]}
    assert "portfolio_snapshot" in modes
    assert "ledger_derived" in modes
    assert "related_entities_baseline" in modes

    rendered = json.dumps(contract).lower()
    assert "host owns all nav" in rendered
    assert "current_nav" in rendered


def test_explain_input_accepts_hyphenated_slug() -> None:
    proc = _run(["--skill", "fund-analysis", "--explain-input", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["doc_slug"] == "fund-analysis"


def test_explain_input_for_mcp_skill_lists_manifest_capabilities() -> None:
    proc = _run(["--skill", "news_research", "--explain-input", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    contract = out["input_contract"]
    assert contract["required_mcp_capabilities"] == [
        "web_search",
        "financial_news",
    ]
    rendered = json.dumps(contract).lower()
    assert "mcp_responses" in rendered
    assert "real provider calls belong to the external host" in rendered


def test_existing_list_skills_command_still_works() -> None:
    proc = _run(["--list-skills", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["ok"] is True
    assert {skill["runtime_id"] for skill in out["skills"]} >= {
        "fund_analysis",
        "decision_support",
        "news_research",
        "sentiment_analysis",
        "thesis_generation",
    }
