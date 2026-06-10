"""OpenCode plugin runtime smoke test (v0.4.6 install-packaging-smoke).

This test focuses on the runtime behavior of the OpenCode plugin
from a clean install surface perspective:

- ``node --check opencode.plugin.js`` must succeed (syntax validity).
- The plugin must be dynamically importable from Node and the
  helper functions must be callable through the public test harness
  (the plugin intentionally does not export ``listSkills``,
  ``readSkillDoc``, or ``runtimeHint`` in production; the test
  harness strips the optional @opencode-ai/plugin import block and
  re-exports them for testability).
- ``listSkills()`` must return ``primary_skill == "fund-analysis"``,
  ``supporting_skills`` of exactly four canonical supporting slugs,
  and a ``skills`` array of length 5.
- ``readSkillDoc`` must accept the canonical hyphenated slug
  ``fund-analysis`` and reject:
  - the underscore runtime ID ``fund_analysis``;
  - the underscore runtime ID ``decision_support``;
  - the archived persona ``fund-analyst``;
  - the path-traversal attempt ``../README.md``.
- ``runtimeHint`` must accept both ``fund-analysis`` and
  ``fund_analysis`` and resolve both to the same Python class.
- The startup log message must not classify ``fund-analysis`` as a
  supporting skill.

This test does NOT require the OpenCode binary. It uses ``node``
directly to dynamically import the plugin and exercise the pure
helper functions.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILE = ROOT / "opencode.plugin.js"

CANONICAL_SLUGS = (
    "fund-analysis",
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
)
PRIMARY = "fund-analysis"
SUPPORTING = (
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
)


def _has_node() -> bool:
    for candidate in ("node", "bun"):
        try:
            subprocess.run(
                [candidate, "--version"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False


NODE_AVAILABLE = _has_node()
requires_node = pytest.mark.skipif(
    not NODE_AVAILABLE, reason="node (or bun) is not available on test host"
)


# ---------------------------------------------------------------------------
# Plugin: syntax check
# ---------------------------------------------------------------------------


@requires_node
def test_plugin_syntax_is_valid():
    """``node --check`` must succeed on opencode.plugin.js."""
    result = subprocess.run(
        ["node", "--check", str(PLUGIN_FILE)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"opencode.plugin.js failed `node --check`: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Plugin: dynamic import + test harness
# ---------------------------------------------------------------------------


def _stage_test_harness() -> Path:
    """Return the on-disk path of a test-harness copy of the plugin.

    The harness strips the optional ``@opencode-ai/plugin`` import
    block and re-exports the internal helper functions
    (``listSkills``, ``readSkillDoc``, ``runtimeHint``) so the test
    can call them through ``import()``. The production plugin
    exports ``buildStartupLogMessage``, ``FundAgentPlugin``, and
    ``default`` only; the harness re-exports are staging-only and
    do not modify the production source.
    """
    source = PLUGIN_FILE.read_text(encoding="utf-8")
    stub = (
        "let toolHelper = null;\n"
        "let toolSchema = null;\n"
        "function buildTools() { return {}; }\n"
    )
    stripped = re.sub(
        r"let toolHelper = null;\nlet toolSchema = null;[\s\S]*?\n\}\s*\nfunction buildTools[\s\S]*?\n\}",
        stub,
        source,
    )
    if stripped == source:
        raise RuntimeError(
            "test harness could not strip the optional plugin import block"
        )
    stripped += (
        "\n// Test harness only: re-export internal helpers so the\n"
        "// smoke test can call them. This block is not present in\n"
        "// the production plugin source.\n"
        "export { listSkills, readSkillDoc, runtimeHint };\n"
    )
    staged = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".plugin.test.mjs",
        dir=str(PLUGIN_FILE.parent),
        delete=False,
        encoding="utf-8",
    )
    staged.write(stripped)
    staged.close()
    return Path(staged.name)


@requires_node
def test_plugin_can_be_dynamically_imported():
    """The plugin module must be importable from a Node ESM context."""
    staged = _stage_test_harness()
    try:
        harness = (
            "import { pathToFileURL } from 'node:url';\n"
            "const pluginPath = process.argv[1];\n"
            "const mod = await import(pathToFileURL(pluginPath).href);\n"
            "const exports = Object.keys(mod);\n"
            "console.log(JSON.stringify(exports));\n"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", harness, str(staged)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"plugin failed to dynamically import: {result.stderr}"
        )
        exports = json.loads(result.stdout)
        # The plugin must export its runtime entrypoints.
        # ``FundAgentPlugin`` is the OpenCode plugin function;
        # ``default`` is the default export; ``buildStartupLogMessage``
        # is the testable helper added in v0.4.5.
        for name in ("FundAgentPlugin", "default", "buildStartupLogMessage"):
            assert name in exports, (
                f"opencode.plugin.js must export '{name}', got: {exports}"
            )
    finally:
        staged.unlink(missing_ok=True)


def _eval_harness(function_name: str, args: dict) -> dict:
    """Call one of the plugin's helper functions through the test
    harness and return the parsed JSON result. Skips if Node is not
    available."""
    if not NODE_AVAILABLE:
        return {"__skipped__": True}
    staged = _stage_test_harness()
    try:
        harness = (
            "import { pathToFileURL } from 'node:url';\n"
            "const pluginPath = process.argv[1];\n"
            "const fnName = process.argv[2];\n"
            "const fnArgs = JSON.parse(process.argv[3]);\n"
            "const mod = await import(pathToFileURL(pluginPath).href);\n"
            "const fn = mod[fnName];\n"
            "if (typeof fn !== 'function') {\n"
            "  console.error('missing function', fnName);\n"
            "  process.exit(2);\n"
            "}\n"
            "const result = await fn(fnArgs);\n"
            "console.log(JSON.stringify(result));\n"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", harness,
             str(staged), function_name, json.dumps(args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0, (
            f"plugin function {function_name} failed: {result.stderr}"
        )
        return json.loads(result.stdout)
    finally:
        staged.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Plugin: listSkills()
# ---------------------------------------------------------------------------


@requires_node
def test_list_skills_returns_primary_and_four_supporting():
    """``listSkills()`` must declare ``primary_skill`` and exactly
    four ``supporting_skills``."""
    payload = _eval_harness("listSkills", {})
    skills = payload.get("skills", [])
    assert len(skills) == 5, (
        f"listSkills() must return exactly 5 entries, got {len(skills)}"
    )
    assert payload.get("primary_skill") == PRIMARY, (
        f"listSkills() primary_skill must be {PRIMARY!r}, "
        f"got {payload.get('primary_skill')!r}"
    )
    supporting = payload.get("supporting_skills", [])
    assert supporting == list(SUPPORTING), (
        f"listSkills() supporting_skills must be exactly "
        f"{list(SUPPORTING)}, got {supporting!r}"
    )
    # Strict subset guard.
    assert PRIMARY not in supporting, (
        f"fund-analysis must not appear in supporting_skills, got: {supporting}"
    )


# ---------------------------------------------------------------------------
# Plugin: readSkillDoc()
# ---------------------------------------------------------------------------


@requires_node
def test_read_skill_doc_accepts_fund_analysis():
    """``readSkillDoc({slug: 'fund-analysis'})`` must succeed and
    return the SKILL.md content."""
    result = _eval_harness("readSkillDoc", {"slug": "fund-analysis"})
    assert result.get("ok") is True, (
        f"readSkillDoc must accept 'fund-analysis', got {result}"
    )
    assert result.get("skill") == "fund-analysis"
    assert "content" in result
    assert "SKILL.md" in (result.get("path") or "")


@requires_node
def test_read_skill_doc_rejects_fund_analysis():
    """``readSkillDoc({slug: 'fund_analysis'})`` must reject the
    underscore runtime ID."""
    result = _eval_harness("readSkillDoc", {"slug": "fund_analysis"})
    assert result.get("ok") is False, (
        f"readSkillDoc must reject 'fund_analysis', got {result}"
    )
    assert "INVALID_INPUT" in (result.get("error") or "")


@requires_node
def test_read_skill_doc_rejects_decision_support_underscore():
    """``readSkillDoc({slug: 'decision_support'})`` must reject the
    underscore runtime ID, separate from ``fund_analysis``."""
    result = _eval_harness("readSkillDoc", {"slug": "decision_support"})
    assert result.get("ok") is False, (
        f"readSkillDoc must reject 'decision_support', got {result}"
    )
    assert "INVALID_INPUT" in (result.get("error") or "")


@requires_node
def test_read_skill_doc_rejects_fund_analyst():
    """``readSkillDoc({slug: 'fund-analyst'})`` must reject the
    archived legacy persona."""
    result = _eval_harness("readSkillDoc", {"slug": "fund-analyst"})
    assert result.get("ok") is False, (
        f"readSkillDoc must reject 'fund-analyst', got {result}"
    )
    assert "INVALID_INPUT" in (result.get("error") or "")


@requires_node
def test_read_skill_doc_rejects_path_traversal():
    """``readSkillDoc({slug: '../README.md'})`` must reject the
    path-traversal attempt. This is the OpenCode plugin's
    path-traversal guard at the public tool surface."""
    result = _eval_harness("readSkillDoc", {"slug": "../README.md"})
    assert result.get("ok") is False, (
        f"readSkillDoc must reject '../README.md', got {result}"
    )
    # The rejection may be either via slug validation (unknown slug)
    # or via path-traversal guard (unsafe path). Both are valid;
    # the contract is just that the result is ok: false.
    error = result.get("error") or ""
    assert (
        "INVALID_INPUT" in error or "NOT_FOUND" in error or "unsafe" in error
    ), f"unexpected error message: {error!r}"


# ---------------------------------------------------------------------------
# Plugin: runtimeHint()
# ---------------------------------------------------------------------------


@requires_node
def test_runtime_hint_accepts_hyphenated_slug():
    """``runtimeHint({runtime_id: 'fund-analysis'})`` must accept the
    hyphenated agent-facing slug."""
    result = _eval_harness("runtimeHint", {"runtime_id": "fund-analysis"})
    assert result.get("ok") is True, result
    assert result.get("skill") == "fund-analysis"
    assert result.get("runtime_id") == "fund_analysis"


@requires_node
def test_runtime_hint_accepts_underscore_runtime_id():
    """``runtimeHint({runtime_id: 'fund_analysis'})`` must accept the
    underscore Python runtime ID."""
    result = _eval_harness("runtimeHint", {"runtime_id": "fund_analysis"})
    assert result.get("ok") is True, result
    assert result.get("skill") == "fund-analysis"
    assert result.get("runtime_id") == "fund_analysis"


# ---------------------------------------------------------------------------
# Plugin: startup log primary / supporting distinction
# ---------------------------------------------------------------------------


@requires_node
def test_startup_log_does_not_classify_fund_analysis_as_supporting():
    """The startup log message must not list ``fund-analysis`` under
    the ``supporting skills:`` clause. This is the v0.4.5 install
    hardening regression guard."""
    payload = _eval_harness("buildStartupLogMessage", {})
    message = payload.get("message") or ""
    assert "primary skill: fund-analysis" in message, (
        f"startup log must declare 'primary skill: fund-analysis', "
        f"got: {message!r}"
    )
    after_supporting = message.split("supporting skills:", 1)[-1]
    assert "fund-analysis" not in after_supporting, (
        f"startup log must not classify 'fund-analysis' as supporting, "
        f"got: {message!r}"
    )
    # The structured payload must split primary from supporting.
    assert payload.get("primary_skill") == PRIMARY
    assert payload.get("supporting_skills") == list(SUPPORTING)
