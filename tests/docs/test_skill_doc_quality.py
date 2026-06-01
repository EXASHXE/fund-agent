"""Regression tests for skill-pack documentation quality.

These tests catch obvious regressions in agent-facing docs:

- No broken placeholder strings like ``skills//SKILL.md`` or stray TODO/FIXME/TBD.
- Canonical SKILL.md files are not compressed into one-liners.
- No canonical doc claims ``fund-agent`` owns network or data fetching.
- The personal-fund-report workflow doc has all required sections.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
WORKFLOW_DOC = ROOT / "docs" / "workflows" / "personal-fund-report.md"

CANONICAL_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "host-integration.md",
    ROOT / "docs" / "plugin-api.md",
    ROOT / "docs" / "agent-host-quickstart.md",
    ROOT / "docs" / "host-compatibility.md",
    ROOT / "docs" / "skill-io-examples.md",
    ROOT / "docs" / "release-checklist.md",
    ROOT / "docs" / "maintenance.md",
    ROOT / "docs" / "archive" / "legacy-system.md",
    ROOT / "skills" / "README.md",
    ROOT / "docs" / "workflows" / "personal-fund-report.md",
]


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text())
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def test_no_broken_skill_placeholders_in_canonical_docs():
    """Canonical docs must not contain broken placeholders like 'skills//SKILL.md'."""
    patterns = [
        re.compile(r"skills//SKILL\.md"),
        re.compile(r"skills/<>/SKILL\.md"),
    ]
    for path in CANONICAL_DOCS:
        if not path.exists():
            continue
        text = path.read_text()
        for pat in patterns:
            assert not pat.search(text), f"{path} contains broken placeholder: {pat.pattern}"


def test_no_stray_todo_fixme_tbd_in_canonical_skill_docs():
    """Canonical skill docs must not contain stray TODO/FIXME/TBD markers."""
    docs = [SKILLS_DIR / "README.md", WORKFLOW_DOC]
    for skill_id in _manifest_skill_ids():
        docs.append(SKILLS_DIR / _slug(skill_id) / "SKILL.md")
    docs.append(SKILLS_DIR / "fund-analyst" / "SKILL.md")

    bad = re.compile(r"\b(TODO|FIXME|TBD)\b")
    for path in docs:
        if not path.exists():
            continue
        text = path.read_text()
        # Allow TODO/FIXME in code blocks (rare here), but flag in prose.
        # Strip fenced code blocks before checking prose.
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        assert not bad.search(stripped), f"{path} contains TODO/FIXME/TBD marker"


def test_canonical_skill_md_files_are_not_compressed():
    """Canonical SKILL.md files must have enough lines to be readable."""
    for skill_id in _manifest_skill_ids():
        path = SKILLS_DIR / _slug(skill_id) / "SKILL.md"
        assert path.exists(), f"missing SKILL.md for {skill_id}"
        lines = path.read_text().splitlines()
        assert len(lines) >= 50, (
            f"{path} has only {len(lines)} lines — looks compressed"
        )


def test_canonical_docs_do_not_claim_fund_agent_fetches_data():
    """Canonical docs must not claim ``fund-agent`` fetches fund, NAV, or market data."""
    forbidden_phrases = [
        "fund-agent fetches",
        "fund-agent will fetch",
        "fund-agent automatically fetches",
        "fund-agent handles fetching",
        "fund-agent owns fetching",
    ]
    for path in CANONICAL_DOCS:
        if not path.exists():
            continue
        text = path.read_text().lower()
        for phrase in forbidden_phrases:
            assert phrase not in text, (
                f"{path} implies fund-agent owns data fetching: '{phrase}'"
            )


def test_personal_fund_report_workflow_has_all_required_sections():
    """personal-fund-report.md must contain all 15 required sections."""
    assert WORKFLOW_DOC.exists()
    text = WORKFLOW_DOC.read_text()
    required_sections = [
        "1. User request",
        "2. Objective interpretation",
        "3. Data collection checklist",
        "4. Required vs optional data",
        "5. When to ask the user for missing data",
        "6. When to proceed with PARTIAL analysis",
        "7. Minimal payload",
        "8. Expanded payload",
        "9. Calling FundAnalysisSkill",
        "10. Generating a report without formal decisions",
        "11. When to escalate to DecisionSupportSkill",
        "12. Calling DecisionSupportSkill",
        "13. Report section template",
        "14. Warning and uncertainty language",
        "15. Evidence appendix guidance",
    ]
    for heading in required_sections:
        assert heading in text, f"personal-fund-report.md missing section: {heading}"


def test_personal_fund_report_workflow_states_host_owns_data():
    """personal-fund-report.md must state the host owns data fetching."""
    text = WORKFLOW_DOC.read_text().lower()
    # Allow flexible wording like "the host owns data fetching",
    # even if split across line wraps.
    normalized = re.sub(r"\s+", " ", text)
    assert "host owns data fetching" in normalized
    assert "fund-agent" in normalized
    assert "does not fetch" in normalized
