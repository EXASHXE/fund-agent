"""Install smoke tests — validate that fund-agent is importable and runnable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import tomllib

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_package_metadata_version_matches_version_file():
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == version


def test_manifest_loads_after_install_like_import():
    from src.skillpack.loader import load_skillpack_manifest
    manifest = load_skillpack_manifest()
    assert manifest.name == "fund-agent"


def test_all_skill_runtimes_resolve():
    from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
    manifest = load_skillpack_manifest()
    for skill in manifest.skills:
        cls = resolve_runtime(skill.runtime)
        assert cls is not None, f"Failed to resolve {skill.name}: {skill.runtime}"


def test_minimal_host_demo_subprocess_outputs_json():
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_news_to_decision.py"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Demo failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert "decision" in data or "artifacts" in data


def test_install_smoke_does_not_require_research_os():
    content = (PROJECT_ROOT / "examples" / "minimal_host_news_to_decision.py").read_text(encoding="utf-8")
    assert "src.core.research_os" not in content
    assert "import legacy" not in content
    assert "from legacy" not in content
