"""Documentation surface tests for the Superpowers-compatible skill collection.

The v0.4.4+ skill surface is documented across:

- `README.md` (top-level project narrative)
- `skills/README.md` (Markdown-first skill directory policy)
- `skills/<slug>/SKILL.md` (per-skill agent-facing instructions)
- `docs/install/opencode.md` (OpenCode install)
- `docs/install/codex.md` (Codex install)
- `.opencode/INSTALL.md` (project-local OpenCode install)
- `docs/workflows/personal-fund-report.md` (host workflow for the
  `分析下我的基金给出报告` request)

These tests verify that the docs:

1. Explain the primary / supporting split.
2. Mention the Superpowers-style composable Markdown skill collection.
3. State that the OpenCode install starts with `fund-analysis` and
   loads supporting skills only when the subtask matches.
4. Do not contain broken placeholders like `skills//SKILL.md`.
5. State that underscore skill directories are not installed /
   exposed.
6. State that the archived `fund-analyst` persona is not installed /
   exposed.
"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "skills" / "README.md",
    ROOT / "skills" / "SKILL.md",
    ROOT / ".opencode" / "INSTALL.md",
    ROOT / "docs" / "install" / "opencode.md",
    ROOT / "docs" / "install" / "codex.md",
    ROOT / "docs" / "install" / "manual-host.md",
    ROOT / "docs" / "workflows" / "personal-fund-report.md",
    ROOT / "docs" / "host-integration.md",
    ROOT / "docs" / "plugin-api.md",
    ROOT / "docs" / "agent-host-quickstart.md",
    ROOT / "docs" / "host-compatibility.md",
    ROOT / "docs" / "skill-io-examples.md",
    ROOT / "docs" / "release-checklist.md",
    ROOT / "docs" / "maintenance.md",
    ROOT / "docs" / "CONTRACT_FREEZE.md",
]

PRIMARY_SKILL = "fund-analysis"
SUPPORTING_SKILLS = [
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# README and skills/README: primary vs supporting skills
# ---------------------------------------------------------------------------


def test_readme_explains_primary_skill():
    """The top-level README must explain that `fund-analysis` is the
    primary / default skill."""
    text = _text(ROOT / "README.md").lower()
    assert "primary" in text, "README.md must mention the primary skill"
    assert "default" in text, "README.md must mention the default skill"
    # The primary skill must be the hyphenated slug.
    assert f"`{PRIMARY_SKILL}`" in (ROOT / "README.md").read_text(
        encoding="utf-8"
    ), f"README.md must reference `{PRIMARY_SKILL}`"


def test_readme_explains_supporting_skills():
    """The top-level README must list the four supporting skills."""
    text = _text(ROOT / "README.md")
    for slug in SUPPORTING_SKILLS:
        assert f"`{slug}`" in text, (
            f"README.md must reference supporting skill `{slug}`"
        )


def test_skills_readme_explains_primary_and_supporting():
    """skills/README.md must mark `fund-analysis` as primary / default
    and the four others as supporting skills, with a clear table."""
    text = _text(ROOT / "skills" / "README.md").lower()
    assert "primary" in text, "skills/README.md must say 'primary'"
    assert "default" in text, "skills/README.md must say 'default'"
    assert "supporting" in text, "skills/README.md must say 'supporting'"
    raw = _text(ROOT / "skills" / "README.md")
    assert f"`{PRIMARY_SKILL}`" in raw
    for slug in SUPPORTING_SKILLS:
        assert f"`{slug}`" in raw, (
            f"skills/README.md must reference supporting skill `{slug}`"
        )


# ---------------------------------------------------------------------------
# OpenCode install docs: Superpowers-style collection
# ---------------------------------------------------------------------------


def test_opencode_install_md_mentions_superpowers_compatible_collection():
    """The .opencode/INSTALL.md must mention the Superpowers-compatible
    composable Markdown skill collection."""
    text = _text(ROOT / ".opencode" / "INSTALL.md").lower()
    assert "superpowers" in text or "composable" in text, (
        ".opencode/INSTALL.md must mention the Superpowers-style "
        "composable skill collection"
    )


def test_opencode_install_md_starts_with_fund_analysis():
    """The .opencode/INSTALL.md must instruct the user to start with
    the primary skill `fund-analysis`."""
    text = _text(ROOT / ".opencode" / "INSTALL.md")
    assert "fund-analysis" in text, (
        ".opencode/INSTALL.md must mention fund-analysis"
    )
    # The instruction should make clear that supporting skills are
    # loaded only when their description matches.
    assert "supporting" in text.lower(), (
        ".opencode/INSTALL.md must mention supporting skills"
    )


def test_docs_install_opencode_md_mentions_superpowers_compatible():
    """docs/install/opencode.md must mention the Superpowers-compatible
    composable Markdown skill collection."""
    text = _text(ROOT / "docs" / "install" / "opencode.md").lower()
    assert "superpowers" in text or "composable" in text, (
        "docs/install/opencode.md must mention the Superpowers-style "
        "composable skill collection"
    )


def test_docs_install_opencode_md_starts_with_fund_analysis():
    """docs/install/opencode.md must say to start with fund-analysis
    and load supporting skills only when the subtask matches."""
    text = _text(ROOT / "docs" / "install" / "opencode.md")
    assert "fund-analysis" in text, (
        "docs/install/opencode.md must mention fund-analysis"
    )
    assert "supporting" in text.lower(), (
        "docs/install/opencode.md must mention supporting skills"
    )


def test_docs_install_codex_md_explains_skill_collection():
    """docs/install/codex.md must explain the new skill surface and
    state that fund-analysis is the primary / default."""
    text = _text(ROOT / "docs" / "install" / "codex.md")
    assert "fund-analysis" in text, (
        "docs/install/codex.md must mention fund-analysis"
    )
    assert "primary" in text.lower() or "default" in text.lower(), (
        "docs/install/codex.md must say fund-analysis is primary/default"
    )
    for slug in SUPPORTING_SKILLS:
        assert f"`{slug}`" in text or slug in text, (
            f"docs/install/codex.md must reference `{slug}`"
        )


# ---------------------------------------------------------------------------
# Personal fund report workflow doc: start with fund-analysis
# ---------------------------------------------------------------------------


def test_personal_fund_report_workflow_says_start_with_fund_analysis():
    """The personal-fund-report.md workflow doc must instruct hosts
    to start with the primary skill `fund-analysis` for the
    `分析下我的基金给出报告` user request."""
    doc = ROOT / "docs" / "workflows" / "personal-fund-report.md"
    text = _text(doc)
    assert "FundAnalysisSkill" in text or "fund-analysis" in text or "fund_analysis" in text, (
        "personal-fund-report.md must reference fund-analysis / FundAnalysisSkill"
    )
    lower = text.lower()
    # The workflow doc should be clear that the report flow starts
    # with fund-analysis and is report-only by default.
    assert "report" in lower, "personal-fund-report.md must mention 'report'"
    assert "fund-analysis" in lower or "fund_analysis" in lower, (
        "personal-fund-report.md must reference fund-analysis / fund_analysis"
    )


# ---------------------------------------------------------------------------
# No broken placeholders
# ---------------------------------------------------------------------------


def test_no_broken_skill_path_placeholders_in_canonical_docs():
    """No canonical doc may contain broken placeholders like
    `skills//SKILL.md` or `skills/<>/SKILL.md` (empty placeholder)."""
    patterns = [
        re.compile(r"skills//SKILL\.md"),
        re.compile(r"skills/<>/SKILL\.md"),
    ]
    for path in CANONICAL_DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            assert not pat.search(text), (
                f"{path} contains broken placeholder: {pat.pattern}"
            )


# ---------------------------------------------------------------------------
# No underscore skill directories installed / exposed
# ---------------------------------------------------------------------------


def test_canonical_docs_do_not_advertise_underscore_skill_dirs():
    """Canonical docs must not advertise underscore skill directories
    (e.g. `skills/fund_analysis/`) as part of the install surface. The
    only place underscore skill names should appear is in the
    manifest runtime ID column of the skill README's mapping table,
    or in an explicit "removed / not part of v0.4.4+ surface"
    explanation paragraph in `skills/README.md`."""
    for path in CANONICAL_DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # The skills/README.md mapping table is allowed to show the
        # underscore Python runtime ID alongside the hyphenated slug.
        # The same doc is also allowed to mention underscore skill
        # directories in an explanatory paragraph about their removal.
        if path.name == "README.md" and path.parent.name == "skills":
            for line in text.splitlines():
                if not any(
                    u in line
                    for u in [
                        "fund_analysis",
                        "news_research",
                        "sentiment_analysis",
                        "thesis_generation",
                    ]
                ):
                    continue
                # Allowed: table row mapping slug to underscore ID;
                # explanatory paragraph that says these are removed
                # / archived / not part of the surface.
                stripped = line.strip()
                assert (
                    stripped.startswith("|")
                    or stripped.startswith("-")
                    or "no longer" in stripped
                    or "compatibility" in stripped
                    or "not part" in stripped
                    or "removed" in stripped
                    or "archive" in stripped
                ), (
                    f"{path} references an underscore skill directory "
                    f"outside the mapping table or explanation: {line!r}"
                )
            continue
        # All other canonical docs must not mention underscore skill
        # directory paths as install locations.
        for underscore in [
            "skills/fund_analysis/",
            "skills/news_research/",
            "skills/sentiment_analysis/",
            "skills/thesis_generation/",
        ]:
            assert underscore not in text, (
                f"{path} references the removed underscore directory "
                f"'{underscore}'"
            )


# ---------------------------------------------------------------------------
# fund-analyst is archived, not installed
# ---------------------------------------------------------------------------


def test_canonical_docs_state_fund_analyst_is_archived():
    """Canonical docs must state that the legacy `fund-analyst`
    persona material is archived, not installed, not a runtime skill.
    Where `fund-analyst` is mentioned, it must be in the context of
    being archived / not installed."""
    install_docs = [
        ROOT / "README.md",
        ROOT / "skills" / "README.md",
        ROOT / "skills" / "SKILL.md",
        ROOT / ".opencode" / "INSTALL.md",
        ROOT / "docs" / "install" / "opencode.md",
        ROOT / "docs" / "install" / "codex.md",
    ]
    for path in install_docs:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "fund-analyst" not in text:
            # If a doc does not mention fund-analyst at all, that is
            # also fine — the v0.4.4+ surface has removed it from
            # the active install surface.
            continue
        lower = text.lower()
        # If `fund-analyst` IS mentioned, the doc must put it in an
        # archived / not-installed / not-runtime context.
        assert (
            "archive" in lower
            or "archived" in lower
            or "not a runtime" in lower
            or "not installed" in lower
            or "not a skill" in lower
            or "docs/archive" in lower
        ), (
            f"{path} mentions 'fund-analyst' but does not clearly mark "
            f"it as archived / not installed / not a runtime skill"
        )


def test_archive_fund_analyst_readme_exists():
    """The archive README must exist and explain the archive status."""
    readme = ROOT / "docs" / "archive" / "fund-analyst" / "README.md"
    assert readme.exists(), (
        "docs/archive/fund-analyst/README.md must exist"
    )
    text = readme.read_text(encoding="utf-8").lower()
    assert "archived" in text, (
        "docs/archive/fund-analyst/README.md must say 'archived'"
    )
    assert "not a runtime" in text or "not installed" in text, (
        "docs/archive/fund-analyst/README.md must say it is not a "
        "runtime skill / not installed"
    )
