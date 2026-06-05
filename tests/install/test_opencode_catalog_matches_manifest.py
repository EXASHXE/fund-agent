"""Manifest <-> OpenCode plugin catalog consistency tests.

Parses opencode.plugin.js SKILL_CATALOG via regex (no JS parser dependency)
and cross-checks against skillpack/fund-agent.skillpack.yaml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"
PLUGIN_PATH = ROOT / "opencode.plugin.js"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _parse_plugin_catalog() -> list[dict]:
    """Extract SKILL_CATALOG entries from opencode.plugin.js using regex."""
    text = PLUGIN_PATH.read_text(encoding="utf-8")

    catalog_match = re.search(
        r"const SKILL_CATALOG\s*=\s*Object\.freeze\(\[(.+?)\]\)",
        text,
        re.DOTALL,
    )
    assert catalog_match, "Could not find SKILL_CATALOG in opencode.plugin.js"
    catalog_body = catalog_match.group(1)

    entries = []
    obj_pattern = re.compile(
        r"Object\.freeze\(\{(.+?)\}\)",
        re.DOTALL,
    )
    for obj_match in obj_pattern.finditer(catalog_body):
        body = obj_match.group(1)
        entry = {}

        runtime_id_m = re.search(r'runtime_id:\s*"([^"]+)"', body)
        if runtime_id_m:
            entry["runtime_id"] = runtime_id_m.group(1)

        doc_slug_m = re.search(r'doc_slug:\s*"([^"]+)"', body)
        if doc_slug_m:
            entry["doc_slug"] = doc_slug_m.group(1)

        runtime_class_m = re.search(r'runtime_class:\s*"([^"]+)"', body)
        if runtime_class_m:
            entry["runtime_class"] = runtime_class_m.group(1)

        role_m = re.search(r'role:\s*"([^"]+)"', body)
        if role_m:
            entry["role"] = role_m.group(1)

        requires_mcp_m = re.search(r"requires_mcp:\s*\[([^\]]*)\]", body)
        if requires_mcp_m:
            raw = requires_mcp_m.group(1).strip()
            if raw:
                entry["requires_mcp"] = [
                    s.strip().strip('"').strip("'") for s in raw.split(",")
                ]
            else:
                entry["requires_mcp"] = []

        produces_m = re.search(r"produces:\s*\[([^\]]*)\]", body)
        if produces_m:
            raw = produces_m.group(1).strip()
            if raw:
                entry["produces"] = [
                    s.strip().strip('"').strip("'") for s in raw.split(",")
                ]
            else:
                entry["produces"] = []

        if "runtime_id" in entry:
            entries.append(entry)

    return entries


def _plugin_version() -> str:
    text = PLUGIN_PATH.read_text(encoding="utf-8")
    m = re.search(r'PLUGIN_VERSION\s*=\s*"([^"]+)"', text)
    assert m, "Could not find PLUGIN_VERSION in opencode.plugin.js"
    return m.group(1)


def test_plugin_version_matches_manifest_version():
    mv = _manifest()["version"]
    pv = _plugin_version()
    assert pv == mv, (
        f"opencode.plugin.js PLUGIN_VERSION={pv!r} != "
        f"skillpack manifest version={mv!r}"
    )


def test_manifest_skill_count_matches_plugin_catalog_count():
    manifest_skills = _manifest()["skills"]
    catalog = _parse_plugin_catalog()
    assert len(catalog) == len(manifest_skills), (
        f"manifest has {len(manifest_skills)} skills but "
        f"opencode.plugin.js SKILL_CATALOG has {len(catalog)} entries"
    )


def test_each_manifest_skill_appears_as_plugin_runtime_id():
    manifest_skills = _manifest()["skills"]
    catalog = _parse_plugin_catalog()
    catalog_ids = {e["runtime_id"] for e in catalog}
    for skill in manifest_skills:
        assert skill["name"] in catalog_ids, (
            f"manifest skill '{skill['name']}' not found in plugin "
            f"SKILL_CATALOG runtime_ids: {sorted(catalog_ids)}"
        )


def test_each_plugin_runtime_class_matches_manifest_runtime():
    manifest_skills = {s["name"]: s for s in _manifest()["skills"]}
    catalog = _parse_plugin_catalog()
    for entry in catalog:
        rid = entry["runtime_id"]
        assert rid in manifest_skills, (
            f"plugin catalog runtime_id '{rid}' not in manifest skills"
        )
        expected = manifest_skills[rid]["runtime"]
        actual = entry["runtime_class"]
        assert actual == expected, (
            f"plugin catalog runtime_class for '{rid}' is {actual!r} "
            f"but manifest runtime is {expected!r}"
        )


def test_each_plugin_requires_mcp_matches_manifest():
    manifest_skills = {s["name"]: s for s in _manifest()["skills"]}
    catalog = _parse_plugin_catalog()
    for entry in catalog:
        rid = entry["runtime_id"]
        expected = sorted(manifest_skills[rid].get("requires_mcp", []))
        actual = sorted(entry.get("requires_mcp", []))
        assert actual == expected, (
            f"plugin catalog requires_mcp for '{rid}' is {actual!r} "
            f"but manifest requires_mcp is {expected!r}"
        )


def test_each_plugin_role_matches_manifest():
    manifest_skills = {s["name"]: s for s in _manifest()["skills"]}
    catalog = _parse_plugin_catalog()
    for entry in catalog:
        rid = entry["runtime_id"]
        expected = manifest_skills[rid].get("role", "supporting")
        actual = entry.get("role", "supporting")
        assert actual == expected, (
            f"plugin catalog role for '{rid}' is {actual!r} "
            f"but manifest role is {expected!r}"
        )


def test_manifest_primary_skill_is_fund_analysis_and_plugin_marks_primary():
    manifest = _manifest()
    assert manifest["primary_skill"] == "fund-analysis", (
        f"manifest primary_skill is {manifest['primary_skill']!r}, "
        f"expected 'fund-analysis'"
    )
    catalog = _parse_plugin_catalog()
    fa = [e for e in catalog if e["runtime_id"] == "fund_analysis"]
    assert len(fa) == 1, "plugin catalog missing fund_analysis entry"
    assert fa[0]["role"] == "primary", (
        f"plugin catalog fund_analysis role is {fa[0]['role']!r}, "
        f"expected 'primary'"
    )


def test_manifest_supporting_skills_match_plugin_supporting():
    manifest = _manifest()
    manifest_supporting = set(manifest.get("supporting_skills", []))
    catalog = _parse_plugin_catalog()
    plugin_supporting = {
        e["doc_slug"] for e in catalog if e.get("role") == "supporting"
    }
    assert plugin_supporting == manifest_supporting, (
        f"manifest supporting_skills={sorted(manifest_supporting)} != "
        f"plugin supporting slugs={sorted(plugin_supporting)}"
    )


def test_plugin_does_not_expose_underscore_doc_slugs():
    catalog = _parse_plugin_catalog()
    for entry in catalog:
        slug = entry.get("doc_slug", "")
        assert "_" not in slug, (
            f"plugin SKILL_CATALOG exposes underscore doc_slug "
            f"'{slug}' for runtime_id '{entry['runtime_id']}'. "
            f"Agent-facing slugs must be hyphenated."
        )


def test_plugin_does_not_expose_fund_analyst_as_installable_skill():
    catalog = _parse_plugin_catalog()
    for entry in catalog:
        assert entry["runtime_id"] != "fund-analyst", (
            "plugin SKILL_CATALOG exposes 'fund-analyst' as an "
            "installable skill. fund-analyst is archived legacy material."
        )
        assert entry["doc_slug"] != "fund-analyst", (
            "plugin SKILL_CATALOG exposes 'fund-analyst' doc slug. "
            "fund-analyst is archived legacy material."
        )
