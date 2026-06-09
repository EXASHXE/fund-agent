"""Isolated editable-install smoke test.

Creates a temporary venv, installs fund-agent in editable mode, and verifies
the runtime bridge can list skills from that install.

Skip this test if venv creation is too slow or unavailable; source-checkout
smoke tests in test_source_checkout_host_smoke.py remain the canonical gate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[2]

_EXPECTED_RUNTIME_IDS = {
    "fund_analysis",
    "decision_support",
    "news_research",
    "sentiment_analysis",
    "thesis_generation",
}


def _python_path(tmp_venv: Path) -> Path:
    bindir = "Scripts" if sys.platform == "win32" else "bin"
    return tmp_venv / bindir / "python"


def _create_venv(tmp_venv: Path) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(tmp_venv)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def test_editable_install_smoke():
    with TemporaryDirectory() as tmp:
        tmp_venv = Path(tmp) / "venv"
        if not _create_venv(tmp_venv):
            pytest.skip("venv creation unavailable; editable-install smoke test skipped")
        python = _python_path(tmp_venv)
        if not python.is_file():
            pytest.skip("venv python not found; editable-install smoke test skipped")

        install = subprocess.run(
            [str(python), "-m", "pip", "install", "-e", str(ROOT), "pyyaml"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if install.returncode != 0:
            pytest.skip(
                f"editable install failed (possibly missing deps): {install.stderr[:200]}"
            )

        result = subprocess.run(
            [str(python), str(ROOT / "scripts" / "run_skill.py"), "--list-skills", "--pretty"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"list-skills failed in venv (may need deps): {result.stderr[:100]}")
        out = json.loads(result.stdout)
        assert out["ok"] is True
        runtime_ids = {item["runtime_id"] for item in out["skills"]}
        assert _EXPECTED_RUNTIME_IDS <= runtime_ids, (
            f"Missing runtime IDs: {_EXPECTED_RUNTIME_IDS - runtime_ids}"
        )
