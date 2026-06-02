"""Tests for runtime bridge manifest resolution.

The bridge resolves runtime classes from the manifest
``skillpack/fund-agent.skillpack.yaml`` via the existing
``src.skillpack.loader``. It must not hardcode the runtime classes
or import legacy code.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_list_skills_resolves_all_five_manifest_runtime_ids():
    """All five manifest runtime IDs must be listed by --list-skills."""
    proc = _run_cli(["--list-skills"])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    runtime_ids = {entry["runtime_id"] for entry in payload["skills"]}
    for expected in [
        "fund_analysis",
        "decision_support",
        "news_research",
        "sentiment_analysis",
        "thesis_generation",
    ]:
        assert expected in runtime_ids, (
            f"manifest resolution must list {expected!r}, got {runtime_ids!r}"
        )


def test_list_skills_includes_runtime_path_for_each_skill():
    """Each listed skill must carry the manifest ``runtime`` field
    (the ``module:attribute`` path) so the bridge can resolve the
    class without hardcoding."""
    proc = _run_cli(["--list-skills"])
    payload = json.loads(proc.stdout)
    for entry in payload["skills"]:
        runtime = entry.get("runtime") or ""
        assert ":" in runtime, (
            f"runtime path must be module:attribute, got {runtime!r}"
        )
        module, _, attr = runtime.partition(":")
        assert module.startswith("src."), (
            f"runtime module must start with 'src.', got {module!r}"
        )
        assert attr, f"runtime attribute must be non-empty, got {runtime!r}"


def test_list_skills_includes_doc_slug_mapping():
    """Each entry should expose the agent-facing hyphenated doc_slug
    alongside the Python runtime_id."""
    proc = _run_cli(["--list-skills"])
    payload = json.loads(proc.stdout)
    runtime_to_slug = {entry["runtime_id"]: entry["doc_slug"] for entry in payload["skills"]}
    assert runtime_to_slug == {
        "fund_analysis": "fund-analysis",
        "decision_support": "decision-support",
        "news_research": "news-research",
        "sentiment_analysis": "sentiment-analysis",
        "thesis_generation": "thesis-generation",
    }


def test_hyphen_slug_is_accepted_as_skill_argument(tmp_path: Path):
    """The bridge accepts hyphenated agent-facing slugs as a
    documented convenience; they must resolve to the same runtime
    class as the underscore runtime_id."""
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({"payload": {}}), encoding="utf-8")
    proc = _run_cli(["--skill", "fund-analysis", "--input", str(input_path)])
    assert proc.returncode == 0, (
        f"hyphen slug 'fund-analysis' must resolve via manifest, got "
        f"returncode={proc.returncode}, stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("skill_name") == "fund_analysis", (
        f"slug must map to fund_analysis, got {payload!r}"
    )


def test_underscore_runtime_id_is_accepted():
    proc = _run_cli(["--skill", "fund_analysis", "--input", "/dev/null"])
    # /dev/null is empty, so the bridge will report INVALID_INPUT
    # but must still resolve the skill name.
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is False
    # The error should be about input, not about the skill name.
    code = payload.get("error", {}).get("code")
    assert code in {"INVALID_INPUT", "JSON_SERIALIZATION_FAILED"}, (
        f"expected input/serialization error, got code={code!r}"
    )


def test_bridge_does_not_import_legacy_code():
    """The bridge module must not import legacy modules."""
    from src.skillpack import run_skill  # noqa: F401  (import side effect)
    import inspect
    source = inspect.getsource(run_skill)
    forbidden_substrings = [
        "src.legacy",
        "from legacy",
        "import legacy",
        "src.core.research_os",
        "from src.core.research_os",
        "import src.core.research_os",
    ]
    for needle in forbidden_substrings:
        assert needle not in source, (
            f"runtime bridge must not import legacy code: {needle!r}"
        )


def test_bridge_does_not_import_provider_sdks():
    """The bridge must not import any provider SDK module."""
    from src.skillpack import run_skill  # noqa: F401
    import inspect
    source = inspect.getsource(run_skill)
    forbidden_sdks = [
        "tavily",
        "finnhub",
        "exa",
        "firecrawl",
        "reddit",
        "akshare",
        "openai",
        "anthropic",
        "langchain",
    ]
    # We allow these to appear inside docstring disclaimers; the
    # bridge explicitly says it does not import them. Match against
    # the actual import lines.
    import_lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            import_lines.append(line)
    import_blob = "\n".join(import_lines).lower()
    for sdk in forbidden_sdks:
        assert sdk not in import_blob, (
            f"runtime bridge must not import provider SDK '{sdk}'"
        )
