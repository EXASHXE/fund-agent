"""Runtime bridge entrypoint smoke tests.

Verifies that the runtime bridge CLI works correctly from source checkout
via both ``scripts/run_skill.py`` and ``python -m src.skillpack.run_skill``.
Semantic tests use in-process bridge; CLI wiring tests stay subprocess.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.bridge_runner import (
    run_bridge_inprocess_json,
    run_bridge_inprocess_metadata,
    run_bridge_inprocess_text,
)

ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL_SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run_module(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "src.skillpack.run_skill"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def _stderr_text(result: subprocess.CompletedProcess) -> str:
    return result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")


class TestListSkills:
    def test_list_skills_returns_ok(self):
        data = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
        assert data.get("ok") is True

    def test_list_skills_lists_five_skills(self):
        data = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
        assert len(data.get("skills", [])) == 5

    @pytest.mark.subprocess
    def test_list_skills_via_module(self):
        result = _run_module(["--list-skills", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
        data = json.loads(stdout)
        assert data.get("ok") is True


class TestExplainInput:
    def test_explain_input_fund_analysis(self):
        data = run_bridge_inprocess_metadata(skill="fund_analysis", explain_input=True, pretty=True)
        assert data.get("ok") is True
        assert data.get("skill_name") == "fund_analysis"

    def test_explain_input_decision_support(self):
        data = run_bridge_inprocess_metadata(skill="decision_support", explain_input=True, pretty=True)
        assert data.get("ok") is True

    def test_explain_input_thesis_generation(self):
        data = run_bridge_inprocess_metadata(skill="thesis_generation", explain_input=True, pretty=True)
        assert data.get("ok") is True


class TestValidateInput:
    def test_validate_input_cn_fund_7d(self):
        input_text = (ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json").read_text(encoding="utf-8")
        data = run_bridge_inprocess_metadata(skill="fund_analysis", validate_input=True, input_text=input_text, pretty=True)
        assert data.get("ok") is True


class TestEmitReport:
    def test_emit_report_markdown(self):
        input_text = (ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json").read_text(encoding="utf-8")
        stdout = run_bridge_inprocess_text(skill="fund_analysis", input_text=input_text, emit_report="markdown")
        assert "# " in stdout or "## " in stdout
        try:
            json.loads(stdout)
            pytest.fail("expected Markdown output, got JSON")
        except json.JSONDecodeError:
            pass


class TestDecisionSupport:
    def test_decision_support_single_active_buy(self):
        input_text = (ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json").read_text(encoding="utf-8")
        data = run_bridge_inprocess_json(skill="decision_support", input_text=input_text, pretty=True)
        assert data.get("ok") is True
        assert data.get("skill_name") == "decision_support"


class TestThesisGeneration:
    def test_thesis_generation_evidence_graph(self):
        input_text = (ROOT / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json").read_text(encoding="utf-8")
        data = run_bridge_inprocess_json(skill="thesis_generation", input_text=input_text, pretty=True)
        assert data.get("ok") is True
        assert data.get("skill_name") == "thesis_generation"


class TestHyphenatedSlugs:
    @pytest.mark.parametrize("slug", [
        "fund-analysis",
        "decision-support",
        "thesis-generation",
    ])
    def test_hyphenated_slug_resolves(self, slug):
        data = run_bridge_inprocess_metadata(skill=slug, explain_input=True, pretty=True)
        assert data.get("ok") is True

    @pytest.mark.parametrize("slug", [
        "fund-analysis",
        "decision-support",
        "thesis-generation",
    ])
    def test_hyphenated_slug_runs_skill(self, slug):
        runtime_id = slug.replace("-", "_")
        if runtime_id == "fund_analysis":
            input_file = ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json"
        elif runtime_id == "decision_support":
            input_file = ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json"
        elif runtime_id == "thesis_generation":
            input_file = ROOT / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json"
        else:
            pytest.skip(f"no fixture for {runtime_id}")
        input_text = input_file.read_text(encoding="utf-8")
        data = run_bridge_inprocess_json(skill=slug, input_text=input_text, pretty=True)
        assert data.get("ok") is True


class TestModuleEntrypoint:
    @pytest.mark.subprocess
    def test_python_m_src_skillpack_run_skill_list_skills(self):
        result = _run_module(["--list-skills", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
        data = json.loads(stdout)
        assert data.get("ok") is True

    @pytest.mark.subprocess
    def test_python_m_src_skillpack_run_skill_explain_input(self):
        result = _run_module(["--skill", "fund_analysis", "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
        data = json.loads(stdout)
        assert data.get("ok") is True
