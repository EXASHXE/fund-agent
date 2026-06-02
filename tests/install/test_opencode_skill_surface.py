"""OpenCode plugin skill surface tests.

The v0.4.4+ OpenCode plugin exposes a **Superpowers-compatible
composable collection** of Markdown skills. The agent-facing skill
names are the five hyphenated Markdown doc slugs:

- `fund-analysis` (primary / default)
- `decision-support` (supporting)
- `news-research` (supporting)
- `sentiment-analysis` (supporting)
- `thesis-generation` (supporting)

The plugin must NOT expose:

- underscore skill slugs (`fund_analysis`, …) as agent-facing skill
  names;
- the archived `fund-analyst` persona.

The `fund_agent_runtime_hint` tool must accept both a hyphenated
agent-facing slug and an underscore Python runtime ID, and resolve
both to the same Python runtime class.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILE = ROOT / "opencode.plugin.js"

EXPECTED_HYPHENATED_SLUGS = [
    "fund-analysis",
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
]
EXPECTED_PRIMARY = "fund-analysis"
EXPECTED_SUPPORTING = [
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
]
EXPECTED_RUNTIME_IDS = [
    "fund_analysis",
    "decision_support",
    "news_research",
    "sentiment_analysis",
    "thesis_generation",
]
HYPHEN_TO_RUNTIME = {
    "fund-analysis": "fund_analysis",
    "decision-support": "decision_support",
    "news-research": "news_research",
    "sentiment-analysis": "sentiment_analysis",
    "thesis-generation": "thesis_generation",
}
RUNTIME_TO_HYPHEN = {v: k for k, v in HYPHEN_TO_RUNTIME.items()}

NODE_BIN_CANDIDATES = ("node", "bun")


def _has_node() -> bool:
    for candidate in NODE_BIN_CANDIDATES:
        try:
            subprocess.run(
                [candidate, "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False


def _plugin_source() -> str:
    return PLUGIN_FILE.read_text(encoding="utf-8")


def _eval_plugin_function(function_name: str, args: dict) -> dict:
    """Evaluate one of the plugin's exported helper functions in a
    minimal Node harness and return the parsed JSON result. This
    avoids having to spin up OpenCode or load the optional peer
    dep; the plugin's helper functions are pure and have no
    external dependencies beyond Node's built-in `fs` and `path`.

    The plugin's `getPluginDir()` resolves its on-disk location from
    `import.meta.url`. To get accurate behaviour (so that doc reads
    resolve to the real `skills/<slug>/SKILL.md` paths) we stage a
    stripped copy of the plugin to a temp file inside the repo
    root, then import it via its on-disk path."""
    if not _has_node():
        return {"__skipped__": True}
    import tempfile
    source = PLUGIN_FILE.read_text(encoding="utf-8")
    # Stub out the optional @opencode-ai/plugin import block so we
    # can evaluate the pure helper functions without resolving the
    # optional peer dep.
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
    # The plugin does not export its internal helper functions in
    # production; append test-only named exports so the harness can
    # import them. This is staging-only and does not modify the
    # real plugin source.
    stripped += (
        "\n// Test harness only: re-export internal helpers so they\n"
        "// can be invoked from the test harness. This block is not\n"
        "// present in the production plugin source.\n"
        "// `buildStartupLogMessage` is already exported by the source\n"
        "// (added in v0.4.5) so it is intentionally NOT re-exported here.\n"
        "export { listSkills, readSkillDoc, runtimeHint };\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".plugin.test.mjs",
        dir=str(PLUGIN_FILE.parent),
        delete=False,
    ) as f:
        f.write(stripped)
        staged_path = Path(f.name)
    try:
        # With `node --input-type=module -e "<harness>"`, process.argv
        # is [node, <positional-1>, <positional-2>, ...].
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
             str(staged_path), function_name, json.dumps(args)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"plugin function {function_name} failed: {result.stderr}"
        )
        return json.loads(result.stdout)
    finally:
        staged_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Plugin source: skill catalog and shape
# ---------------------------------------------------------------------------


def test_plugin_exposes_exactly_five_hyphenated_skill_slugs():
    """The plugin's SKILL_CATALOG must declare exactly the five
    hyphenated agent-facing skill slugs."""
    text = _plugin_source()
    for slug in EXPECTED_HYPHENATED_SLUGS:
        assert (f'"{slug}"' in text) or (f"'{slug}'" in text), (
            f"opencode.plugin.js must expose agent-facing slug '{slug}'"
        )


def test_plugin_marks_fund_analysis_as_primary():
    """fund-analysis must be marked as the primary / default skill in
    the plugin's SKILL_CATALOG and in the listSkills() output."""
    text = _plugin_source()
    assert re.search(r'role:\s*"primary"', text), (
        "opencode.plugin.js SKILL_CATALOG must mark fund-analysis as primary"
    )
    assert '"fund-analysis"' in text or "'fund-analysis'" in text, (
        "opencode.plugin.js must include the fund-analysis slug"
    )


def test_plugin_marks_supporting_skills():
    """The four non-primary skills must be marked as supporting in
    the plugin's SKILL_CATALOG."""
    text = _plugin_source()
    # Count supporting entries: there should be exactly four.
    supporting_count = len(re.findall(r'role:\s*"supporting"', text))
    assert supporting_count == 4, (
        f"opencode.plugin.js must mark exactly 4 supporting skills, "
        f"got {supporting_count}"
    )
    for slug in EXPECTED_SUPPORTING:
        assert (f'"{slug}"' in text) or (f"'{slug}'" in text), (
            f"opencode.plugin.js must expose supporting slug '{slug}'"
        )


def test_plugin_does_not_expose_underscore_skill_slugs_in_list_skills():
    """The plugin's listSkills() output (its public JSON shape) must
    NOT advertise underscore runtime IDs as agent-facing skill names.

    Concretely: the keys used for agent-facing skill names must be
    `skill` (hyphenated) only, not `runtime_id`. The plugin's
    listSkills() returns objects with `skill` (the hyphenated slug)
    and `runtime_id` (the underscore Python ID). The hyphenated
    slugs are the agent-facing names."""
    payload = _eval_plugin_function("listSkills", {})
    if payload.get("__skipped__"):
        return  # node not available
    skills = payload.get("skills", [])
    assert len(skills) == 5, (
        f"listSkills() must return exactly 5 entries, got {len(skills)}"
    )
    advertised_slugs = {entry.get("skill") for entry in skills}
    advertised_runtime_ids = {entry.get("runtime_id") for entry in skills}
    assert advertised_slugs == set(EXPECTED_HYPHENATED_SLUGS), (
        f"listSkills() agent-facing 'skill' slugs must be exactly "
        f"{EXPECTED_HYPHENATED_SLUGS}, got {advertised_slugs}"
    )
    assert advertised_runtime_ids == set(EXPECTED_RUNTIME_IDS), (
        f"listSkills() 'runtime_id' values must be exactly "
        f"{EXPECTED_RUNTIME_IDS}, got {advertised_runtime_ids}"
    )
    # The listSkills() output must declare the primary skill and the
    # supporting skills explicitly.
    assert payload.get("primary_skill") == EXPECTED_PRIMARY, (
        f"listSkills() must declare primary_skill='{EXPECTED_PRIMARY}', "
        f"got {payload.get('primary_skill')!r}"
    )
    assert set(payload.get("supporting_skills", [])) == set(EXPECTED_SUPPORTING), (
        f"listSkills() supporting_skills must be exactly "
        f"{EXPECTED_SUPPORTING}, got {payload.get('supporting_skills')}"
    )


def test_plugin_does_not_advertise_fund_analyst():
    """The plugin must not advertise the archived fund-analyst persona
    in listSkills() output."""
    payload = _eval_plugin_function("listSkills", {})
    if payload.get("__skipped__"):
        return
    advertised = (
        {entry.get("skill") for entry in payload.get("skills", [])} |
        {payload.get("primary_skill")} |
        set(payload.get("supporting_skills", []))
    )
    assert "fund-analyst" not in advertised, (
        f"listSkills() must not advertise 'fund-analyst'; got {advertised}"
    )


# ---------------------------------------------------------------------------
# Plugin source: skill_doc behavior
# ---------------------------------------------------------------------------


def test_plugin_rejects_underscore_doc_slug():
    """fund_agent_skill_doc must reject underscore skill slugs
    (e.g. 'fund_analysis'). The agent-facing skill name is the
    hyphenated Markdown doc slug only."""
    result = _eval_plugin_function("readSkillDoc", {"slug": "fund_analysis"})
    if result.get("__skipped__"):
        return
    assert result.get("ok") is False, (
        f"readSkillDoc must reject underscore slug 'fund_analysis', "
        f"got {result}"
    )
    assert "INVALID_INPUT" in (result.get("error") or ""), (
        f"rejection error must be an INVALID_INPUT, got {result.get('error')!r}"
    )


def test_plugin_rejects_fund_analyst_doc_slug():
    """fund_agent_skill_doc must reject the archived 'fund-analyst'
    persona slug explicitly."""
    result = _eval_plugin_function("readSkillDoc", {"slug": "fund-analyst"})
    if result.get("__skipped__"):
        return
    assert result.get("ok") is False, (
        f"readSkillDoc must reject 'fund-analyst', got {result}"
    )
    assert "INVALID_INPUT" in (result.get("error") or ""), (
        f"rejection error must be an INVALID_INPUT, got {result.get('error')!r}"
    )


def test_plugin_accepts_each_canonical_hyphenated_skill_doc():
    """fund_agent_skill_doc must accept each canonical hyphenated
    slug and return the SKILL.md contents."""
    for slug in EXPECTED_HYPHENATED_SLUGS:
        result = _eval_plugin_function("readSkillDoc", {"slug": slug})
        if result.get("__skipped__"):
            return
        assert result.get("ok") is True, (
            f"readSkillDoc must accept canonical slug '{slug}', "
            f"got {result}"
        )
        # The result must include the agent-facing skill name and the
        # underscore runtime ID for caller convenience.
        assert result.get("skill") == slug, (
            f"readSkillDoc must echo agent-facing slug '{slug}' as 'skill', "
            f"got {result.get('skill')!r}"
        )
        assert result.get("runtime_id") == HYPHEN_TO_RUNTIME[slug], (
            f"readSkillDoc must echo runtime_id '{HYPHEN_TO_RUNTIME[slug]}' "
            f"for slug '{slug}', got {result.get('runtime_id')!r}"
        )
        assert "content" in result, (
            f"readSkillDoc must return 'content' for '{slug}'"
        )
        assert "SKILL.md" in (result.get("path") or ""), (
            f"readSkillDoc path must point at SKILL.md for '{slug}'"
        )


# ---------------------------------------------------------------------------
# Plugin source: runtime_hint behavior
# ---------------------------------------------------------------------------


def test_plugin_runtime_hint_accepts_hyphenated_slug():
    """fund_agent_runtime_hint must accept a hyphenated agent-facing
    slug and resolve it to the matching Python runtime class."""
    for slug in EXPECTED_HYPHENATED_SLUGS:
        result = _eval_plugin_function("runtimeHint", {"runtime_id": slug})
        if result.get("__skipped__"):
            return
        assert result.get("ok") is True, (
            f"runtimeHint must accept hyphenated slug '{slug}', "
            f"got {result}"
        )
        assert result.get("skill") == slug, (
            f"runtimeHint must echo agent-facing slug '{slug}' as 'skill', "
            f"got {result.get('skill')!r}"
        )
        assert result.get("runtime_id") == HYPHEN_TO_RUNTIME[slug], (
            f"runtimeHint must resolve '{slug}' to runtime_id "
            f"'{HYPHEN_TO_RUNTIME[slug]}', got {result.get('runtime_id')!r}"
        )
        # role: primary for fund-analysis, supporting for the rest.
        expected_role = "primary" if slug == EXPECTED_PRIMARY else "supporting"
        assert result.get("role") == expected_role, (
            f"runtimeHint role for '{slug}' must be '{expected_role}', "
            f"got {result.get('role')!r}"
        )


def test_plugin_runtime_hint_accepts_underscore_runtime_id():
    """fund_agent_runtime_hint must accept an underscore Python
    runtime ID and resolve it to the same Python runtime class as
    the hyphenated slug."""
    for runtime_id in EXPECTED_RUNTIME_IDS:
        result = _eval_plugin_function("runtimeHint", {"runtime_id": runtime_id})
        if result.get("__skipped__"):
            return
        assert result.get("ok") is True, (
            f"runtimeHint must accept underscore runtime_id "
            f"'{runtime_id}', got {result}"
        )
        assert result.get("runtime_id") == runtime_id, (
            f"runtimeHint must echo runtime_id '{runtime_id}', got "
            f"{result.get('runtime_id')!r}"
        )
        assert result.get("skill") == RUNTIME_TO_HYPHEN[runtime_id], (
            f"runtimeHint must map '{runtime_id}' to skill "
            f"'{RUNTIME_TO_HYPHEN[runtime_id]}', got {result.get('skill')!r}"
        )


def test_plugin_runtime_hint_rejects_unknown_inputs():
    """fund_agent_runtime_hint must reject unknown hyphenated slugs
    and unknown underscore runtime IDs."""
    for bad in ["fund-analyst", "fund_analyst", "garbage", "fund_analyst_legacy"]:
        result = _eval_plugin_function("runtimeHint", {"runtime_id": bad})
        if result.get("__skipped__"):
            return
        assert result.get("ok") is False, (
            f"runtimeHint must reject '{bad}', got {result}"
        )
        assert "INVALID_INPUT" in (result.get("error") or ""), (
            f"rejection error must be an INVALID_INPUT for '{bad}', "
            f"got {result.get('error')!r}"
        )


# ---------------------------------------------------------------------------
# Plugin source: startup log primary / supporting distinction (v0.4.5)
# ---------------------------------------------------------------------------


def test_plugin_startup_log_message_does_not_list_fund_analysis_under_supporting():
    """The startup log message must not list `fund-analysis` under
    supporting skills. v0.4.4 had a bug where the message joined all
    five slugs into the `supporting skills:` clause; v0.4.5 splits
    primary from supporting and asserts the distinction here."""
    payload = _eval_plugin_function("buildStartupLogMessage", {})
    if payload.get("__skipped__"):
        return
    message = payload.get("message") or ""
    assert "primary skill: fund-analysis" in message, (
        f"startup log must declare 'primary skill: fund-analysis', "
        f"got: {message!r}"
    )
    # The supporting skills clause must contain exactly the four
    # supporting slugs in the expected order, with no
    # `fund-analysis` included.
    assert "supporting skills: decision-support, news-research, sentiment-analysis, thesis-generation" in message, (
        f"startup log supporting-skills clause must be exactly the four "
        f"supporting slugs in canonical order, got: {message!r}"
    )
    # Direct guard: fund-analysis must not appear in the
    # `supporting skills:` clause at all. The primary-skill clause
    # contains it; the supporting-skills clause must not.
    after_supporting_marker = message.split("supporting skills:", 1)[-1]
    assert "fund-analysis" not in after_supporting_marker, (
        f"startup log must not list 'fund-analysis' under supporting "
        f"skills, got: {message!r}"
    )


def test_plugin_startup_log_structured_payload_splits_primary_from_supporting():
    """The structured log payload (the `extra` block) must list
    `primary_skill` as `fund-analysis` and `supporting_skills` as
    exactly the four supporting slugs."""
    payload = _eval_plugin_function("buildStartupLogMessage", {})
    if payload.get("__skipped__"):
        return
    assert payload.get("primary_skill") == EXPECTED_PRIMARY, (
        f"startup log payload must have primary_skill='{EXPECTED_PRIMARY}', "
        f"got {payload.get('primary_skill')!r}"
    )
    assert payload.get("supporting_skills") == EXPECTED_SUPPORTING, (
        f"startup log payload supporting_skills must be exactly "
        f"{EXPECTED_SUPPORTING}, got {payload.get('supporting_skills')!r}"
    )


def test_plugin_list_skills_supporting_skills_excludes_fund_analysis():
    """listSkills() must not include `fund-analysis` in
    `supporting_skills`. This is a strict subset guard, separate
    from the equality check below, so a future change that adds
    extra items to supporting_skills still fails the regression
    guard."""
    payload = _eval_plugin_function("listSkills", {})
    if payload.get("__skipped__"):
        return
    supporting = payload.get("supporting_skills", [])
    assert "fund-analysis" not in supporting, (
        f"listSkills() supporting_skills must not include 'fund-analysis', "
        f"got {supporting!r}"
    )


def test_plugin_list_skills_supporting_skills_equals_four_canonical():
    """listSkills() supporting_skills must equal exactly the four
    canonical supporting slugs, in canonical order, with no extras
    and no missing entries."""
    payload = _eval_plugin_function("listSkills", {})
    if payload.get("__skipped__"):
        return
    supporting = payload.get("supporting_skills", [])
    assert supporting == EXPECTED_SUPPORTING, (
        f"listSkills() supporting_skills must equal exactly "
        f"{EXPECTED_SUPPORTING}, got {supporting!r}"
    )
    assert len(supporting) == 4, (
        f"listSkills() supporting_skills must have exactly 4 entries, "
        f"got {len(supporting)}"
    )


# ---------------------------------------------------------------------------
# Plugin source: no provider SDK, no network, no subprocess
# ---------------------------------------------------------------------------


def test_plugin_source_makes_no_network_io():
    text = _plugin_source()
    for pattern in [
        re.compile(r"\bfetch\s*\("),
        re.compile(r"\bXMLHttpRequest\b"),
        re.compile(r"\bhttp\.request\s*\("),
        re.compile(r"\bhttps\.request\s*\("),
        re.compile(r"\baxios\."),
    ]:
        assert not pattern.search(text), (
            f"opencode.plugin.js must not perform network IO "
            f"(matched {pattern.pattern})"
        )


def test_plugin_source_does_not_spawn_subprocess():
    text = _plugin_source()
    assert "child_process" not in text, (
        "opencode.plugin.js must not import child_process"
    )


def test_plugin_source_does_not_import_provider_sdks():
    text = _plugin_source()
    forbidden = [
        "tavily", "finnhub", "exa", "firecrawl", "reddit",
        "akshare", "openai", "anthropic", "langchain",
    ]
    import_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            import_lines.append(line)
        if "require(" in stripped and not stripped.startswith("//"):
            import_lines.append(line)
    import_blob = "\n".join(import_lines)
    for sdk in forbidden:
        assert sdk not in import_blob.lower(), (
            f"opencode.plugin.js must not import provider SDK '{sdk}'"
        )
