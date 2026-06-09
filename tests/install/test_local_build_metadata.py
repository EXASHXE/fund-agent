"""Local build metadata dry-run tests.

Inspects source archives and wheels without publishing or installing.
Uses python -m build if available; skips with reason if not installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _has_build() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--help"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def _list_archive_members(path: Path) -> list[str]:
    names: list[str] = []
    if path.suffix == ".gz":
        with tarfile.open(path, "r:gz") as tf:
            for member in tf.getmembers():
                if member.isreg():
                    names.append(member.name)
    elif path.suffix == ".whl":
        with zipfile.ZipFile(path, "r") as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
    return names


@pytest.mark.skipif(not _has_build(), reason="python build module not installed; pip install build to enable")
class TestLocalBuildMetadata:
    def test_build_produces_sdist_and_wheel(self):
        with TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", tmp],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, f"build failed: {result.stderr}"
            files = list(Path(tmp).glob("*.tar.gz"))
            wheels = list(Path(tmp).glob("*.whl"))
            assert len(files) >= 1, f"No sdist built in {tmp}"
            assert len(wheels) >= 1, f"No wheel built in {tmp}"

    def test_sdist_contains_required_files(self):
        required = [
            "pyproject.toml",
            "README.md",
            "skillpack/fund-agent.skillpack.yaml",
            "skillpack/capabilities.yaml",
            "skillpack/tools.yaml",
            "skillpack/contracts.yaml",
            "skillpack/thesis-contracts.yaml",
            "skills/fund-analysis/SKILL.md",
            "skills/decision-support/SKILL.md",
            "skills/news-research/SKILL.md",
            "skills/sentiment-analysis/SKILL.md",
            "skills/thesis-generation/SKILL.md",
            "scripts/run_skill.py",
            "docs/contracts/fund-analysis-input-contract.v1.md",
            "docs/contracts/decision-support-contract.v1.md",
            "docs/contracts/thesis-generation-contract.v1.md",
            "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "examples/decision_support/single_active_buy_with_evidence.json",
            "examples/thesis_generation/thesis_with_mixed_evidence.json",
        ]
        with TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, "-m", "build", "--sdist", "--outdir", tmp],
                cwd=str(ROOT),
                capture_output=True,
                timeout=120,
            )
            sdists = list(Path(tmp).glob("*.tar.gz"))
            if not sdists:
                pytest.skip("No sdist produced; check pyproject build config")
            members = _list_archive_members(sdists[0])
            for req in required:
                found = any(req in m for m in members)
                assert found, f"sdist missing required file: {req}"

    def test_wheel_includes_python_packages(self):
        with TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", tmp],
                cwd=str(ROOT),
                capture_output=True,
                timeout=120,
            )
            wheels = list(Path(tmp).glob("*.whl"))
            if not wheels:
                pytest.skip("No wheel produced; check pyproject build config")
            members = _list_archive_members(wheels[0])
            python_files = [m for m in members if m.endswith(".py")]
            assert len(python_files) > 0, "Wheel contains no Python files"
            source_modules = [m for m in python_files if "src/" in m]
            assert len(source_modules) > 0, "Wheel contains no src/ modules"
            assert any("src/skills_runtime" in m for m in python_files), "Wheel missing skills_runtime"


class TestLocalBuildHelpers:
    def test_build_available_or_documented_skip(self):
        if _has_build():
            pytest.skip("build is installed; skip message not needed")
