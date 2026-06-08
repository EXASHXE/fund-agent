"""Full integration test — real portfolio JSON → FundAnalysis → Evidence → Decision."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.evidence.validators import compile_evidence_graph


def _load_json(name: str) -> dict:
    return json.loads(Path(f"examples/{name}").read_text(encoding="utf-8"))


def test_full_portfolio_flow_from_json():
    payload = _load_json("portfolio_review_200k.json")

    fund_output = FundAnalysisSkill().run(SkillInput(
        task_id="integration-test",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    ))
    assert fund_output.status in ("OK", "PARTIAL")
    assert fund_output.evidence_items
    assert fund_output.artifacts.get("fund_analysis_report")

    compile_result = compile_evidence_graph(fund_output.evidence_items)
    graph = compile_result.graph
    assert len(graph.items) > 0

    portfolio = payload.get("portfolio", {})
    risk_profile = payload.get("risk_profile", {})
    constraints = payload.get("constraints", {})

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="integration-test",
        step_id="decision",
        skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "personal portfolio review",
            "portfolio_context": portfolio,
            "risk_profile": risk_profile,
            "constraints": constraints,
            "target_trade_amount": 5000.0,
            "time_horizon": "6 months",
            "critique_status": "PASS",
        },
    ))
    assert decision_output.status == "OK"
    decision = decision_output.artifacts.get("decision", decision_output.artifacts.get("decisions"))
    assert decision


def test_flow_is_json_serializable():
    payload = _load_json("portfolio_review_200k.json")
    fund_output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="fa", skill_name="fund_analysis", payload=payload,
    ))
    compile_result = compile_evidence_graph(fund_output.evidence_items)

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "portfolio review",
            "portfolio_context": payload.get("portfolio", {}),
            "risk_profile": payload.get("risk_profile", {}),
            "target_trade_amount": 5000.0,
            "time_horizon": "6 months",
            "critique_status": "PASS",
        },
    ))

    serialized = json.dumps({
        "fund_analysis": fund_output.to_dict(),
        "compile_report": compile_result.report.to_dict(),
        "decision_output": decision_output.to_dict(),
    }, default=str)
    assert serialized


def test_flow_does_not_import_research_os_or_legacy():
    example_file = Path("examples/minimal_host_portfolio_review.py")
    tree = ast.parse(example_file.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {"src.core.research_os", "legacy", "src.legacy"}
    assert not (imports & forbidden), f"Forbidden imports found: {imports & forbidden}"


def test_only_decision_support_produces_decision():
    payload = _load_json("portfolio_review_200k.json")
    fund_output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="fa", skill_name="fund_analysis", payload=payload,
    ))

    assert "decision" not in fund_output.artifacts
    assert "execution_ledger" not in fund_output.artifacts

    compile_result = compile_evidence_graph(fund_output.evidence_items)
    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "portfolio review",
            "portfolio_context": payload.get("portfolio", {}),
            "risk_profile": payload.get("risk_profile", {}),
            "target_trade_amount": 5000.0,
            "time_horizon": "6 months",
            "critique_status": "PASS",
        },
    ))

    assert "decision" in decision_output.artifacts or "decisions" in decision_output.artifacts
    assert "execution_ledger" in decision_output.artifacts
