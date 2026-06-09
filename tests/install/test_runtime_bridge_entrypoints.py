"""Runtime bridge entrypoint smoke tests.

Verifies that the runtime bridge CLI works correctly from source checkout
via both ``scripts/run_skill.py`` and ``python -m src.skillpack.run_skill``.
These tests use subprocess to exercise the actual CLI entrypoints without
relying on the global PATH or a console script installation.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL_SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run_bridge(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(RUN_SKILL_SCRIPT)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def _run_module(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "src.skillpack.run_skill"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def _stdout_text(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def _stderr_text(result: subprocess.CompletedProcess) -> str:
    return result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")


def _parse_json(stdout: str) -> dict:
    return json.loads(stdout)


class TestListSkills:
    def test_list_skills_returns_ok(self):
        result = _run_bridge(["--list-skills", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    def test_list_skills_lists_five_skills(self):
        result = _run_bridge(["--list-skills", "--pretty"])
        data = _parse_json(_stdout_text(result))
        assert len(data.get("skills", [])) == 5

    def test_list_skills_via_module(self):
        result = _run_module(["--list-skills", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True


class TestExplainInput:
    def test_explain_input_fund_analysis(self):
        result = _run_bridge(["--skill", "fund_analysis", "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        assert data.get("skill_name") == "fund_analysis"

    def test_explain_input_decision_support(self):
        result = _run_bridge(["--skill", "decision_support", "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    def test_explain_input_thesis_generation(self):
        result = _run_bridge(["--skill", "thesis_generation", "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True


class TestValidateInput:
    def test_validate_input_cn_fund_7d(self):
        result = _run_bridge([
            "--skill", "fund_analysis",
            "--input", str(ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json"),
            "--validate-input", "--pretty",
        ])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True


class TestEmitReport:
    def test_emit_report_markdown(self):
        result = _run_bridge([
            "--skill", "fund_analysis",
            "--input", str(ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json"),
            "--emit-report", "markdown",
        ])
        stdout = _stdout_text(result)
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        assert "# " in stdout or "## " in stdout
        try:
            json.loads(stdout)
            pytest.fail("expected Markdown output, got JSON")
        except json.JSONDecodeError:
            pass


class TestDecisionSupport:
    def test_decision_support_single_active_buy(self):
        result = _run_bridge([
            "--skill", "decision_support",
            "--input", str(ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json"),
            "--pretty",
        ])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        assert data.get("skill_name") == "decision_support"


class TestThesisGeneration:
    def test_thesis_generation_evidence_graph(self):
        result = _run_bridge([
            "--skill", "thesis_generation",
            "--input", str(ROOT / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json"),
            "--pretty",
        ])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        assert data.get("skill_name") == "thesis_generation"


class TestHyphenatedSlugs:
    @pytest.mark.parametrize("slug", [
        "fund-analysis",
        "decision-support",
        "thesis-generation",
    ])
    def test_hyphenated_slug_resolves(self, slug):
        result = _run_bridge(["--skill", slug, "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    @pytest.mark.parametrize("slug", [
        "fund-analysis",
        "decision-support",
        "thesis-generation",
    ])
    def test_hyphenated_slug_runs_skill(self, slug):
        runtime_id = slug.replace("-", "_")
        if runtime_id == "fund_analysis":
            input_file = str(ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json")
        elif runtime_id == "decision_support":
            input_file = str(ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json")
        elif runtime_id == "thesis_generation":
            input_file = str(ROOT / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json")
        else:
            pytest.skip(f"no fixture for {runtime_id}")
        result = _run_bridge([
            "--skill", slug,
            "--input", input_file,
            "--pretty",
        ])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True


class TestModuleEntrypoint:
    def test_python_m_src_skillpack_run_skill_list_skills(self):
        result = _run_module(["--list-skills", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    def test_python_m_src_skillpack_run_skill_explain_input(self):
        result = _run_module(["--skill", "fund_analysis", "--explain-input", "--pretty"])
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
