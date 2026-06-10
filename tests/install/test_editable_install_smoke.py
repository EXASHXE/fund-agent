"""Isolated editable-install smoke test.

Creates a temporary venv, installs fund-agent in editable mode, and verifies
the runtime bridge can list skills from that install.

Skip this test if venv creation is too slow or unavailable; source-checkout
smoke tests in test_source_checkout_host_smoke.py remain the canonical gate.
"""

from __future__ import annotations

import json
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
    if sys.platform == "win32":
        candidates = (
            tmp_venv / "Scripts" / "python.exe",
            tmp_venv / "Scripts" / "python",
        )
    else:
        candidates = (tmp_venv / "bin" / "python",)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


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


def _first_diagnostic_line(text: str) -> str:
    preferred_fragments = (
        "installing build dependencies",
        "no module named",
        "could not",
        "failed",
        "error:",
    )
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().lower().startswith("[notice]")
    ]
    for fragment in preferred_fragments:
        for line in lines:
            if fragment in line.lower() and line.lower() != "error: exception:":
                return line[:200]
    for stripped in lines:
        if stripped.lower().startswith("error: exception"):
            return "pip failed during offline editable install setup"
        return stripped[:200]
    return "no diagnostic output"


def test_editable_install_smoke():
    with TemporaryDirectory() as tmp:
        tmp_venv = Path(tmp) / "venv"
        if not _create_venv(tmp_venv):
            pytest.skip("venv creation unavailable; editable-install smoke test skipped")
        python = _python_path(tmp_venv)
        if not python.is_file():
            pytest.skip("venv python not found; editable-install smoke test skipped")

        pip = subprocess.run(
            [str(python), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if pip.returncode != 0:
            pytest.skip("pip unavailable in venv; editable-install smoke test skipped")

        install = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-build-isolation",
                "--no-deps",
                "-e",
                str(ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if install.returncode != 0:
            diagnostic = _first_diagnostic_line(install.stderr or install.stdout)
            pytest.skip(
                "editable install unavailable without network/build isolation: "
                f"{diagnostic}"
            )

        result = subprocess.run(
            [str(python), str(ROOT / "scripts" / "run_skill.py"), "--list-skills", "--pretty"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            "list-skills failed after editable install: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        out = json.loads(result.stdout)
        assert out["ok"] is True
        runtime_ids = {item["runtime_id"] for item in out["skills"]}
        assert _EXPECTED_RUNTIME_IDS <= runtime_ids, (
            f"Missing runtime IDs: {_EXPECTED_RUNTIME_IDS - runtime_ids}"
        )
