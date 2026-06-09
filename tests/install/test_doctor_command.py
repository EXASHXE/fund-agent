"""Doctor command tests — verifies host acceptance doctor output and behavior.

Tests:
- run_doctor(include_smoke=False) returns ok=true and status OK.
- run_doctor(include_smoke=True) returns ok=true and status OK.
- Every check has id/status/message/details.
- Missing manifest path returns ok=false or status FAILED.
- python scripts/fund_agent_doctor.py --pretty returns JSON ok=true.
- python -m src.skillpack.doctor --pretty returns JSON ok=true.
- fund-agent-doctor console script is declared in pyproject.toml.
- Output includes package_root and manifest_path metadata.
- No provider API key env vars are required.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR_SCRIPT = ROOT / "scripts" / "fund_agent_doctor.py"


def _run_script(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(DOCTOR_SCRIPT)] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(ROOT))


def _run_module(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "src.skillpack.doctor"] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(ROOT))


def _stdout_text(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


class TestDoctorNoSmoke:
    def test_ok_true(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        assert result.get("ok") is True, f"errors: {result.get('errors')}"

    def test_status_ok(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        assert result.get("status") == "OK"

    def test_checks_have_required_fields(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        for check in result.get("checks", []):
            assert "id" in check
            assert "status" in check
            assert "message" in check
            assert "details" in check

    def test_metadata_has_package_root(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        assert "package_root" in result.get("metadata", {})

    def test_metadata_has_manifest_path(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        assert "manifest_path" in result.get("metadata", {})

    def test_metadata_has_resource_resolution(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=False)
        assert result["metadata"]["resource_resolution"] == "cwd_then_package_root"


class TestDoctorWithSmoke:
    def test_ok_true(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=True)
        assert result.get("ok") is True, f"errors: {result.get('errors')}"

    def test_status_ok(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(include_smoke=True)
        assert result.get("status") == "OK"


class TestDoctorMissingManifest:
    def test_missing_manifest_returns_failed(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(manifest_path="nonexistent/manifest.yaml", include_smoke=False)
        assert result.get("ok") is False or result.get("status") == "FAILED"

    def test_missing_manifest_has_error(self):
        from src.skillpack.doctor import run_doctor
        result = run_doctor(manifest_path="nonexistent/manifest.yaml", include_smoke=False)
        assert len(result.get("errors", [])) > 0


class TestDoctorScript:
    def test_script_pretty_returns_json_ok(self):
        result = _run_script(["--pretty", "--no-smoke"])
        stdout = _stdout_text(result)
        assert result.returncode == 0, f"stderr: {result.stderr.decode('utf-8', errors='replace') if isinstance(result.stderr, bytes) else result.stderr}"
        data = json.loads(stdout)
        assert data.get("ok") is True

    def test_module_pretty_returns_json_ok(self):
        result = _run_module(["--pretty", "--no-smoke"])
        stdout = _stdout_text(result)
        assert result.returncode == 0, f"stderr: {result.stderr.decode('utf-8', errors='replace') if isinstance(result.stderr, bytes) else result.stderr}"
        data = json.loads(stdout)
        assert data.get("ok") is True


class TestDoctorConsoleScript:
    def test_console_script_declared_in_pyproject(self):
        pyproject_path = ROOT / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        assert "fund-agent-doctor" in content
        assert "src.skillpack.doctor:main" in content


class TestDoctorNoApiKeyRequired:
    def test_no_provider_api_key_env_vars(self):
        provider_key_vars = [
            "TAVILY_API_KEY",
            "FINNHUB_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "EXA_API_KEY",
        ]
        for var in provider_key_vars:
            assert os.environ.get(var) is None or os.environ.get(var) == "", (
                f"Doctor should not require {var}"
            )
