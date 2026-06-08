"""Skill docs should reinforce runtime boundary rules."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8"))
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def _doc(skill_id: str) -> str:
    return (SKILLS_DIR / _slug(skill_id) / "SKILL.md").read_text(encoding="utf-8").lower()


def test_canonical_docs_forbid_network_and_provider_bypass():
    for skill_id in _manifest_skill_ids():
        text = _doc(skill_id)
        assert "direct network" in text
        assert "provider sdk" in text


def test_only_decision_support_is_documented_as_formal_decision_producer():
    decision_text = _doc("decision_support")
    assert "only skill allowed to emit `decision` or `executionledger`" in decision_text

    for skill_id in set(_manifest_skill_ids()) - {"decision_support"}:
        text = _doc(skill_id)
        assert "decision_support" in text
        assert "formal `decision`" in text


def test_mcp_skills_document_host_owned_mcp_boundary():
    for skill_id in ("news_research", "sentiment_analysis"):
        text = _doc(skill_id)
        assert "mcphostadapter" in text
        assert "host" in text
        assert "mcp" in text
