"""Tests for realistic example JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

CANONICAL_TRANSACTION_TYPES = frozenset({
    "BUY", "SELL", "DIVIDEND", "FEE", "TRANSFER_IN", "TRANSFER_OUT",
})


def _example_json_files():
    return sorted(
        p for p in EXAMPLES_DIR.glob("*.json")
        if p.name != "fundle_payload.json"
        and not p.name.startswith("runtime_bridge_")
    )


def test_all_examples_load():
    json_files = _example_json_files()
    assert len(json_files) > 0, "No example JSON files found"
    for path in json_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name} is not a dict"


def test_examples_accepted_by_fund_analysis_skill():
    for path in _example_json_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        skill_input = SkillInput(
            task_id="test-examples-load",
            step_id="fund-analysis",
            skill_name="fund_analysis",
            payload=data,
        )
        output = FundAnalysisSkill().run(skill_input)
        assert output.status in ("OK", "PARTIAL"), (
            f"{path.name}: FundAnalysisSkill failed with status={output.status}"
        )


def test_examples_use_canonical_action_field():
    for path in _example_json_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        transactions = data.get("transactions", [])
        if not isinstance(transactions, list):
            continue
        for txn in transactions:
            if not isinstance(txn, dict):
                continue
            txn_type = txn.get("type") or txn.get("action")
            assert txn_type is not None, (
                f"{path.name}: transaction missing 'type'/'action' field: {txn}"
            )
            assert txn_type in CANONICAL_TRANSACTION_TYPES, (
                f"{path.name}: transaction 'type'={txn_type!r} not in canonical set "
                f"{sorted(CANONICAL_TRANSACTION_TYPES)}"
            )
