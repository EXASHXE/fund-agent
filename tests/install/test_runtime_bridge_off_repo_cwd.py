"""Non-repo-root runtime bridge invocation tests.

Verifies that the runtime bridge CLI works correctly when the current
working directory is outside the repository root. This exercises the
centralized resource resolver (``src.skillpack.resources``) that
falls back to ``package_root()`` when relative paths do not resolve
from cwd.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL_SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run_from_tmpdir(
    args: list[str],
    *,
    tmp_dir: Path,
    use_module: bool = False,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    if use_module:
        cmd = [sys.executable, "-m", "src.skillpack.run_skill"] + args
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
    else:
        cmd = [sys.executable, str(RUN_SKILL_SCRIPT)] + args
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        cwd=str(tmp_dir),
        env=env,
    )


def _stdout_text(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def _stderr_text(result: subprocess.CompletedProcess) -> str:
    return result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")


def _parse_json(stdout: str) -> dict:
    return json.loads(stdout)


@pytest.fixture()
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestListSkillsOffRepo:
    def test_list_skills_script_from_tmpdir(self, tmp_dir):
        result = _run_from_tmpdir(["--list-skills", "--pretty"], tmp_dir=tmp_dir)
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    def test_list_skills_module_from_tmpdir(self, tmp_dir):
        result = _run_from_tmpdir(
            ["--list-skills", "--pretty"],
            tmp_dir=tmp_dir,
            use_module=True,
        )
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True


class TestExplainInputOffRepo:
    def test_explain_input_fund_analysis_from_tmpdir(self, tmp_dir):
        result = _run_from_tmpdir(
            ["--skill", "fund_analysis", "--explain-input", "--pretty"],
            tmp_dir=tmp_dir,
        )
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        assert data.get("skill_name") == "fund_analysis"


class TestOutputSchemaOffRepo:
    def test_output_schema_decision_support_from_tmpdir(self, tmp_dir):
        result = _run_from_tmpdir(
            ["--skill", "decision_support", "--output-schema", "--pretty"],
            tmp_dir=tmp_dir,
        )
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        schema = data.get("output_schema", {})
        assert "decision_fields" in schema
        assert "reason_codes" in schema

    def test_output_schema_thesis_generation_from_tmpdir(self, tmp_dir):
        result = _run_from_tmpdir(
            ["--skill", "thesis_generation", "--output-schema", "--pretty"],
            tmp_dir=tmp_dir,
        )
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True
        schema = data.get("output_schema", {})
        assert "thesis_draft_fields" in schema


class TestRunFundAnalysisOffRepo:
    def test_fund_analysis_absolute_input_from_tmpdir(self, tmp_dir):
        input_path = str(ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json")
        result = _run_from_tmpdir(
            ["--skill", "fund_analysis", "--input", input_path, "--pretty"],
            tmp_dir=tmp_dir,
        )
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        data = _parse_json(_stdout_text(result))
        assert data.get("ok") is True

    def test_fund_analysis_emit_report_markdown_from_tmpdir(self, tmp_dir):
        input_path = str(ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json")
        result = _run_from_tmpdir(
            ["--skill", "fund_analysis", "--input", input_path, "--emit-report", "markdown"],
            tmp_dir=tmp_dir,
        )
        stdout = _stdout_text(result)
        assert result.returncode == 0, f"stderr: {_stderr_text(result)}"
        assert "# " in stdout or "## " in stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(stdout)
