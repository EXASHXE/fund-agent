"""DecisionSupportSkill contract tests."""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill


def test_decision_support_skill_outputs_decision_and_ledger():
    output = DecisionSupportSkill().run(_input(evidence_graph=_positive_graph()))

    assert output.status == "OK"
    assert output.artifacts["decision"]["action"] in {"BUY", "INCREASE"}
    assert output.artifacts["decision"]["rationale_anchor"] == ["ev-positive"]
    assert output.artifacts["execution_ledger"]["decisions"][0]["evidence_ids"] == [
        "ev-positive"
    ]


def test_decision_support_downgrades_active_decision_without_anchor():
    output = DecisionSupportSkill().run(
        _input(
            evidence_graph=EvidenceGraph(),
            payload_extra={"requested_action": "BUY"},
        )
    )

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"WAIT", "HOLD"}
    assert "EVIDENCE_MISSING" in decision["decision_reason_codes"]
    assert "DOWNGRADED_ACTIVE_TO_HOLD" in decision["decision_reason_codes"]
    assert decision["blocked_by"]


def test_decision_support_allows_wait_with_insufficient_evidence():
    output = DecisionSupportSkill().run(_input(evidence_graph=EvidenceGraph()))

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"WAIT", "HOLD", "PAUSE_DCA"}
    assert decision["rationale_anchor"] == []
    assert any("Insufficient evidence" in item for item in decision["audit_trail"])


def test_decision_support_is_json_serializable():
    output = DecisionSupportSkill().run(_input(evidence_graph=_positive_graph()))

    json.dumps(output.to_dict())


def test_decision_support_respects_portfolio_trade_caps():
    output = DecisionSupportSkill().run(
        _input(
            evidence_graph=_positive_graph(),
            payload_extra={
                "portfolio_context": {
                    "total_value": 100000.0,
                    "cash_available": 3000.0,
                },
                "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
                "constraints": {"max_buy_amount": 5000.0, "min_trade_amount": 100.0},
                "target_trade_amount": 9000.0,
            },
        )
    )

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"BUY", "INCREASE"}
    assert decision["execution_amount"] == 3000.0


def test_decision_support_downgrades_when_active_amount_is_unsafe():
    output = DecisionSupportSkill().run(
        _input(
            evidence_graph=_positive_graph(),
            payload_extra={
                "portfolio_context": {
                    "total_value": 100000.0,
                    "cash_available": 50.0,
                },
                "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
                "constraints": {"min_trade_amount": 100.0},
                "target_trade_amount": 80.0,
            },
        )
    )

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"HOLD", "WAIT"}
    assert decision["execution_amount"] == 0.0
    assert any("Insufficient evidence or budget" in item for item in decision["audit_trail"])


def test_decision_support_does_not_import_network_or_llm():
    package_path = Path("src/skills_runtime/decision_support")
    imports = _imports_from_package(package_path)
    forbidden = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "openai",
        "anthropic",
        "langchain",
    }

    assert not (imports & forbidden)


def _input(
    evidence_graph: EvidenceGraph,
    payload_extra: dict | None = None,
) -> SkillInput:
    payload = {
        "evidence_graph": evidence_graph.to_dict(),
        "objective": "review fund",
        "time_horizon": "1 year",
        "portfolio_context": {},
        "risk_budget": {},
    }
    payload.update(payload_extra or {})
    return SkillInput(
        task_id="decision-support",
        step_id="decision",
        skill_name="decision_support",
        payload=payload,
    )


def _positive_graph() -> EvidenceGraph:
    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id="ev-positive",
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="positive risk adjusted return signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "quant_tool"},
        )
    )
    return graph


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _imports_from_package(package_path: Path) -> set[str]:
    imports: set[str] = set()
    for file_path in sorted(package_path.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports
