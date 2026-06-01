"""Markdown-first skill document quality tests."""
from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text())
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def _doc(skill_id: str) -> str:
    return (SKILLS_DIR / _slug(skill_id) / "SKILL.md").read_text()


def _has_heading(text: str, heading: str) -> bool:
    return re.search(rf"^##\s+{re.escape(heading)}\b", text, re.MULTILINE | re.IGNORECASE) is not None


def test_canonical_skill_docs_have_required_sections():
    required = [
        "Purpose",
        "When to use",
        "When not to use",
        "Host responsibilities",
        "Inputs",
        "Outputs",
        "Forbidden behavior",
    ]
    for skill_id in _manifest_skill_ids():
        text = _doc(skill_id)
        missing = [heading for heading in required if not _has_heading(text, heading)]
        assert not missing, f"{skill_id} missing headings: {missing}"


def test_fund_analysis_doc_mentions_required_artifacts_and_escalation():
    text = _doc("fund_analysis")
    required_terms = [
        "portfolio_summary",
        "risk_flags",
        "exposure_summary",
        "suggested_rebalance_plan",
        "HardEvidence",
        "warnings",
        "decision_support",
    ]
    for term in required_terms:
        assert term in text


def test_decision_support_doc_mentions_required_policy_terms():
    text = _doc("decision_support")
    required_terms = [
        "EvidenceGraph",
        "Decision",
        "ExecutionLedger",
        "active evidence",
        "WAIT/HOLD",
        "deterministic mode",
    ]
    lower_text = text.lower()
    for term in required_terms:
        assert term.lower() in lower_text
