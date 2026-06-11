"""Test helpers for E2E advisory workflow tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.schemas.decision import Decision, ExecutionLedger
from src.schemas.evidence_graph import EvidenceGraph
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.workflow.evidence_bridge import (
    build_evidence_graph_from_workflow,
    resolve_evidence_source_refs,
    WorkflowEvidenceGraphResult,
)
from src.tools.workflow.final_report import compose_advisory_workflow_report

E2E_FIXTURES_DIR = Path(__file__).parent.parent.parent / "examples" / "e2e_advisory_workflows"

FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "broker_order_id",
    "order_id",
    "order_status",
    "filled_quantity",
    "fill_price",
    "execution_venue",
    "submitted_at",
    "broker",
    "exchange_order_id",
})

FORBIDDEN_FORMAL_ARTIFACT_KEYS = frozenset({
    "decision",
    "decisions",
    "execution_ledger",
    "ledger_summary",
})


def load_e2e_fixture(name: str) -> dict[str, Any]:
    """Load an E2E fixture JSON file."""
    path = E2E_FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"E2E fixture not found: {path}")
    with open(path, "r") as f:
        return json.load(f)


def run_fund_analysis(fixture: dict[str, Any]) -> SkillOutput:
    """Run FundAnalysisSkill against an E2E fixture."""
    skill = FundAnalysisSkill()
    input_obj = SkillInput(
        task_id=fixture.get("scenario_id", "e2e-test"),
        step_id="fa-step",
        skill_name="fund_analysis",
        payload=fixture,
    )
    return skill.run(input_obj)


def run_decision_support(
    fund_analysis_output: SkillOutput,
    fixture: dict[str, Any],
    evidence_bridge_result: WorkflowEvidenceGraphResult | None = None,
) -> SkillOutput:
    """Run DecisionSupportSkill with evidence from fund_analysis and bridge."""
    skill = DecisionSupportSkill()

    payload: dict[str, Any] = {
        "evidence_graph": {},
    }

    if evidence_bridge_result and evidence_bridge_result.graph.items:
        payload["evidence_graph"] = evidence_bridge_result.graph.to_dict()
    else:
        fa_dict = fund_analysis_output.to_dict()
        fa_artifacts = fa_dict.get("artifacts", {})
        payload["evidence_graph"] = _make_minimal_graph(fa_dict).to_dict()

    requested = fixture.get("requested_action")
    if requested:
        payload["requested_action"] = requested

    trade_plan = fixture.get("trade_plan") or fixture.get("requested_trade_plan")
    if trade_plan:
        # Resolve evidence_source_refs deterministically if provided
        if evidence_bridge_result and evidence_bridge_result.graph.items:
            resolved_plan, resolve_warnings = resolve_evidence_source_refs(
                trade_plan, evidence_bridge_result.graph
            )
            payload["trade_plan"] = resolved_plan
        else:
            payload["trade_plan"] = trade_plan
        payload["selected_trade_ids"] = fixture.get("selected_trade_ids", [])

    payload["requested_amount"] = fixture.get("target_trade_amount") or fixture.get("requested_amount", 0)
    payload["portfolio_context"] = fixture.get("portfolio", {})
    payload["risk_profile"] = fixture.get("risk_profile", {})
    payload["constraints"] = fixture.get("constraints", {})
    payload["time_horizon"] = fixture.get("time_horizon", "medium_term")
    payload["objective"] = fixture.get("user_question") or fixture.get("user_intent", "")

    fa_dict = fund_analysis_output.to_dict()
    fa_artifacts = fa_dict.get("artifacts", {})
    for key in (
        "analysis_plan",
        "evidence_gap_diagnostics",
        "profit_protection_diagnostics",
        "benchmark_divergence_diagnostics",
        "right_side_confirmation_diagnostics",
        "event_hype_failure_diagnostics",
        "cash_deployment_diagnostics",
        "redemption_fee_risk",
        "position_contribution",
    ):
        value = fa_artifacts.get(key)
        if value:
            payload[key] = value

    input_obj = SkillInput(
        task_id=fixture.get("scenario_id", "e2e-test"),
        step_id="ds-step",
        skill_name="decision_support",
        payload=payload,
    )
    return skill.run(input_obj)


def build_workflow_evidence(fixture: dict[str, Any], fund_analysis_output: SkillOutput) -> WorkflowEvidenceGraphResult:
    """Build EvidenceGraph from fund_analysis and host evidence."""
    fa_dict = fund_analysis_output.to_dict()
    return build_evidence_graph_from_workflow(
        fund_analysis_output=fa_dict,
        host_news_evidence=fixture.get("news_evidence", []),
        host_sentiment_evidence=fixture.get("sentiment_evidence", []),
        host_benchmark_evidence=fixture.get("benchmark_history", {}),
        host_fee_evidence=fixture.get("fee_schedules", {}),
        host_redemption_evidence=fixture.get("redemption_rules", {}),
        include_diagnostics=True,
    )


def compose_final_report(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
    decision_support_output: SkillOutput | None = None,
    evidence_result: WorkflowEvidenceGraphResult | None = None,
    advisory_intents: list[str] | None = None,
) -> dict[str, Any]:
    """Compose the final advisory workflow report."""
    fa_dict = fund_analysis_output.to_dict()
    ds_dict = decision_support_output.to_dict() if decision_support_output else None
    eg_dict = evidence_result.to_dict() if evidence_result else None

    missing_data = {}
    fa_artifacts = fa_dict.get("artifacts", {})
    if isinstance(fa_artifacts, dict):
        gap = fa_artifacts.get("evidence_gap_diagnostics", {})
        if isinstance(gap, dict):
            missing_data = gap

    language = fixture.get("language", "en")

    if advisory_intents is None:
        from src.skills_runtime.workflow.advisory_intent import classify_advisory_intent
        advisory_intents = classify_advisory_intent(
            host_intent_hint=fixture.get("user_intent"),
            user_question=fixture.get("user_question"),
            requested_action=fixture.get("requested_action"),
        )

    return compose_advisory_workflow_report(
        scenario_id=fixture.get("scenario_id", "unknown"),
        fund_analysis_output=fa_dict,
        decision_support_output=ds_dict,
        evidence_graph_diagnostics=eg_dict,
        missing_data_diagnostics=missing_data,
        language=language,
        advisory_intents=advisory_intents,
    )


def assert_no_formal_decision_in_output(skill_output: SkillOutput) -> None:
    """Assert fund_analysis output does not contain formal Decision/ExecutionLedger."""
    artifacts = skill_output.artifacts or {}
    for key in FORBIDDEN_FORMAL_ARTIFACT_KEYS:
        assert key not in artifacts, (
            f"fund_analysis artifact '{key}' must not be present"
        )


def assert_no_execution_fields(data: Any, path: str = "root") -> None:
    """Recursively assert no broker/order execution fields exist."""
    if isinstance(data, dict):
        for key, value in data.items():
            assert key not in FORBIDDEN_EXECUTION_FIELDS, (
                f"Forbidden execution field '{key}' found at {path}"
            )
            assert_no_execution_fields(value, f"{path}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            assert_no_execution_fields(item, f"{path}[{i}]")


def assert_decision_support_is_only_formal_producer(
    fund_analysis_output: SkillOutput,
    decision_support_output: SkillOutput | None = None,
) -> None:
    """Assert only decision_support produces formal Decision/ExecutionLedger."""
    assert_no_formal_decision_in_output(fund_analysis_output)
    if decision_support_output:
        ds_artifacts = decision_support_output.artifacts or {}
        has_decision = bool(ds_artifacts.get("decision") or ds_artifacts.get("decisions"))
        has_ledger = bool(ds_artifacts.get("execution_ledger"))
        assert has_decision or has_ledger, (
            "decision_support output should contain decision or execution_ledger"
        )


def _make_minimal_graph(fa_dict: dict[str, Any]) -> EvidenceGraph:
    """Make a minimal EvidenceGraph from fund_analysis evidence items."""
    from src.schemas.evidence import EvidenceItem
    from datetime import datetime, timezone

    graph = EvidenceGraph()
    evidence_items = fa_dict.get("evidence_items", [])
    if isinstance(evidence_items, list):
        for item_dict in evidence_items:
            if isinstance(item_dict, dict):
                try:
                    ts = item_dict.get("timestamp")
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts = datetime.now(timezone.utc)
                    ei = EvidenceItem(
                        evidence_id=str(item_dict.get("evidence_id", "")),
                        evidence_type=str(item_dict.get("evidence_type", "HardEvidence")),
                        source_type=str(item_dict.get("source_type", "")),
                        timestamp=ts,
                        related_entities=list(item_dict.get("related_entities", [])),
                        claim=str(item_dict.get("claim", "")),
                        value=item_dict.get("value"),
                        confidence_weight=float(item_dict.get("confidence_weight", 1.0)),
                        direction=str(item_dict.get("direction", "neutral")),
                        provenance=dict(item_dict.get("provenance", {})),
                    )
                    graph.add(ei)
                except Exception:
                    pass
    return graph
