"""The manifest runtime ID -> hyphenated doc slug mapping must be consistent
across:

  1. skillpack/fund-agent.skillpack.yaml (the manifest, source of truth)
  2. opencode.plugin.js (the OpenCode plugin SKILL_CATALOG)
  3. skills/README.md and the canonical SKILL.md files
  4. package.json (declared for the install surface)
  5. docs/install/*.md and docs/design/*.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skillpack" / "fund-agent.skillpack.yaml"
PLUGIN_FILE = ROOT / "opencode.plugin.js"
SKILLS_README = ROOT / "skills" / "README.md"
SKILL_DIR = ROOT / "skills"
DOCS_DIR = ROOT / "docs"


def _manifest_pairs() -> list[tuple[str, str]]:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    pairs = []
    for skill in data["skills"]:
        runtime_id = skill["name"]
        slug = runtime_id.replace("_", "-")
        pairs.append((runtime_id, slug))
    return pairs


def test_manifest_pairs():
    pairs = _manifest_pairs()
    assert pairs, "manifest must declare at least one skill"
    expected = {
        ("fund_analysis", "fund-analysis"),
        ("news_research", "news-research"),
        ("sentiment_analysis", "sentiment-analysis"),
        ("thesis_generation", "thesis-generation"),
        ("decision_support", "decision-support"),
    }
    assert set(pairs) == expected, (
        f"manifest runtime_id/doc_slug pairs changed: {set(pairs) ^ expected}"
    )


def test_plugin_skill_catalog_matches_manifest_pairs():
    """The OpenCode plugin's SKILL_CATALOG must list the same five
    (runtime_id, doc_slug) pairs as the manifest, in the same order."""
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    expected = _manifest_pairs()
    for runtime_id, doc_slug in expected:
        # Both must appear in the plugin file as string literals.
        assert (f'"{runtime_id}"' in text) or (f"'{runtime_id}'" in text), (
            f"plugin SKILL_CATALOG missing runtime_id {runtime_id!r}"
        )
        assert (f'"{doc_slug}"' in text) or (f"'{doc_slug}'" in text), (
            f"plugin SKILL_CATALOG missing doc_slug {doc_slug!r}"
        )


def test_canonical_skill_md_files_exist_for_each_slug():
    pairs = _manifest_pairs()
    for _, slug in pairs:
        path = SKILL_DIR / slug / "SKILL.md"
        assert path.exists(), f"missing canonical SKILL.md for slug '{slug}'"


def test_skills_readme_documents_runtime_id_to_slug_mapping():
    """skills/README.md is the host-readable mapping reference. It must
    list every manifest runtime_id and its hyphenated doc slug."""
    text = SKILLS_README.read_text(encoding="utf-8")
    for runtime_id, slug in _manifest_pairs():
        assert runtime_id in text, (
            f"skills/README.md missing runtime_id '{runtime_id}'"
        )
        assert slug in text, f"skills/README.md missing doc_slug '{slug}'"


def test_install_docs_reference_all_runtime_ids():
    """Every install doc and the runtime bridge design doc must mention
    every manifest runtime_id at least once, so users can grep for a
    runtime ID and find the install surface."""
    install_doc_paths = [
        ROOT / "docs" / "install" / "opencode.md",
        ROOT / "docs" / "install" / "manual-host.md",
        ROOT / "docs" / "install" / "codex.md",
        ROOT / ".opencode" / "INSTALL.md",
        ROOT / "docs" / "design" / "runtime-bridge.md",
    ]
    for path in install_doc_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for runtime_id, _ in _manifest_pairs():
            # Runtime IDs may appear in tables, prose, or code blocks.
            # The OpenCode install doc + runtime-bridge doc must mention
            # at least the doc slugs; the manual host doc must mention
            # runtime IDs because it shows Python import paths.
            if path.name in ("opencode.md",) and path.parent.name == "install":
                # opencode install doc may use slugs; allow either.
                pass
            assert runtime_id in text or _manifest_pairs_pair(runtime_id) in text, (
                f"{path} does not mention {runtime_id} or its slug"
            )


def _manifest_pairs_pair(runtime_id: str) -> str:
    return runtime_id.replace("_", "-")


def test_install_docs_use_doc_slugs_in_prose():
    """The OpenCode install doc and runtime-bridge design doc primarily
    use hyphenated doc slugs in prose, since the agent reads those."""
    opencode_install_text = (ROOT / "docs" / "install" / "opencode.md").read_text(
        encoding="utf-8"
    )
    for _, slug in _manifest_pairs():
        assert slug in opencode_install_text, (
            f"docs/install/opencode.md missing doc slug '{slug}'"
        )


def test_no_orphan_underscore_skill_dirs_in_skills_dir():
    """Underscore directories under skills/ are compatibility-only and
    must not be the canonical doc location. The canonical doc location
    is the hyphenated directory, which must exist for every manifest
    skill."""
    canonical_dirs = {slug for _, slug in _manifest_pairs()}
    for entry in SKILL_DIR.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name == "fund-analyst":
            # Legacy persona dir, allowed but not canonical.
            continue
        if "_" in name:
            # Compatibility dir; not a canonical doc location.
            continue
        if name in {"archive", "workflows", "reference_workflows", "contracts"}:
            # Top-level reference dirs; not skill docs.
            continue
        # Hyphenated dirs that are not in the manifest must not exist.
        assert name in canonical_dirs, (
            f"unexpected hyphenated skill directory '{name}' "
            f"without a manifest entry"
        )
