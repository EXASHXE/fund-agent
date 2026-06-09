"""Skill output contract docs tests.

Verifies that docs/contracts/skill-output-contract.v1.md exists and
documents the canonical error object shape, status values, warnings,
bridge-level errors, and formal Decision boundary.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CONTRACTS = DOCS / "contracts"
START_HERE = DOCS / "START_HERE.md"


def _read_contract() -> str:
    path = CONTRACTS / "skill-output-contract.v1.md"
    assert path.exists(), f"contract doc not found: {path}"
    return path.read_text(encoding="utf-8")


class TestSkillOutputContractDocExists:
    def test_contract_file_exists(self):
        path = CONTRACTS / "skill-output-contract.v1.md"
        assert path.exists()


class TestSkillOutputContractDocContent:
    def test_mentions_code_message_details_recoverable(self):
        text = _read_contract()
        for field in ("code", "message", "details", "recoverable"):
            assert field in text, f"contract doc missing '{field}'"

    def test_mentions_status_values(self):
        text = _read_contract()
        for status in ("OK", "PARTIAL", "FAILED"):
            assert status in text, f"contract doc missing status '{status}'"

    def test_mentions_warnings_are_strings(self):
        text = _read_contract()
        assert "warning" in text.lower()

    def test_mentions_bridge_level_errors(self):
        text = _read_contract()
        assert "bridge" in text.lower()
        assert "INVALID_INPUT" in text or "UNKNOWN_SKILL" in text

    def test_mentions_decision_support_only_formal_decision(self):
        text = _read_contract()
        assert "decision_support" in text
        assert "Decision" in text or "ExecutionLedger" in text


class TestStartHereLinksToSkillOutputContract:
    def test_start_here_links_to_skill_output_contract(self):
        text = START_HERE.read_text(encoding="utf-8")
        assert "skill-output-contract" in text
