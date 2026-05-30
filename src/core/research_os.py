"""Deprecated / optional reference only.

Not required for host integration.
External agents should use skillpack manifest and skills_runtime directly.

This module is retained as an optional reference workflow for tests and
examples. It is not the primary product entrypoint for fund-agent. External
agent hosts should load ``skillpack/fund-agent.skillpack.yaml`` and call
``src.skills_runtime`` handlers directly.

The reference loop demonstrates one possible orchestration of the
fund-research pipeline:

    1. KG query (MUST happen before Planner, enforced here)
    2. Plan generation (Planner receives KG context)
    3. Skill execution (registered skills produce EvidenceItems)
    4. Evidence compilation (compile_evidence_graph)
    5. Critic review (structural checks → PASS / RETRY / FAIL / EXHAUSTED)
    6. Decision generation (DecisionEngine.enforce contract rules)
    7. Ledger construction (LedgerBuilder → ExecutionLedger)

Constraints:
    - Max 3 retries by default (configurable via max_iterations)
    - Circuit breaker on FAIL/EXHAUSTED critique — exits the loop immediately
    - KG MUST be queried before Planner (enforced in code)
    - No LLM / network / IO imports in the main loop
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from src.core.critic import Critic, CritiqueResult
from src.core.decision_engine import DecisionEngine
from src.core.ledger import LedgerBuilder
from src.core.planner import Planner
from src.core.skill_registry import SkillRegistry
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.queries import get_entity_chain, query_exposure
from src.schemas.decision import Decision, ExecutionLedger
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.report import FinalThesis
from src.schemas.research_task import ResearchTask
from src.schemas.skill import SkillInput
from src.tools.evidence.validators import EvidenceGraphCompileResult, compile_evidence_graph


# ── Public API ──────────────────────────────────────────────────────────────────


def run_research_task(
    task: ResearchTask,
    kg: KnowledgeGraph | None = None,
    skill_registry: SkillRegistry | None = None,
    max_iterations: int = 3,
    decision_engine: DecisionEngine | None = None,
    ledger_builder: LedgerBuilder | None = None,
) -> FinalThesis:
    """Main Research OS loop.

    Orchestrates the full fund-research pipeline:
    KG query → Plan → Skill execution → Evidence compile → Critic → Decision → Ledger.

    The loop iterates up to ``max_iterations`` times. After each iteration the
    Critic reviews the accumulated evidence. If the critique is PASS the loop
    exits early. If the critique is FAIL the circuit breaker triggers and the
    loop exits immediately (no retry).

    Args:
        task:             ResearchTask with fund_universe, objective, etc.
        kg:               Optional KnowledgeGraph. Created empty if None.
        skill_registry:   Optional SkillRegistry. Default empty registry if None.
        max_iterations:   Maximum number of retry iterations (default 3).
        decision_engine:  Optional DecisionEngine. Created if None.
        ledger_builder:   Optional LedgerBuilder. Created if None.

    Returns:
        Dict (FinalThesis) with keys:
        - thesis_id, task_id
        - decision (dict or None)
        - ledger (dict or None)
        - evidence_count, iterations
        - critique_status, circuit_broken
        - kg_context_snapshot
        - generated_at (ISO-8601 timestamp)
    """

    # ── Bootstrap ──────────────────────────────────────────────────────────────

    planner = Planner()
    critic = Critic()
    decision_engine = decision_engine or DecisionEngine()
    ledger_builder = ledger_builder or LedgerBuilder()
    from src.core.skill_registry import bootstrap_default_registry
    skill_registry = skill_registry or bootstrap_default_registry()
    kg = kg or KnowledgeGraph()

    all_evidence_items: list[EvidenceItem] = []
    final_decision: Decision | None = None
    final_ledger: ExecutionLedger | None = None
    final_critique: CritiqueResult | None = None
    iteration: int = 0
    skill_errors: list[dict[str, Any]] = []
    failed_steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    skill_artifacts: dict[str, list[dict[str, Any]]] = {}
    iteration_compile_reports: list[dict[str, Any]] = []
    mcp_capability_audit: list[dict[str, Any]] = []

    # ── Step 1: Query KG FIRST (before anything else) ──────────────────────────
    # Enforced: KG context MUST be captured before Planner.plan() is called.
    kg_context: dict[str, Any] = _query_kg_context(kg, task, warnings=warnings)

    # ── Step 2: Generate initial plan (Planner also queries KG internally) ─────
    plan = planner.plan(task, kg)
    plan.kg_context_snapshot = kg_context

    # ── Step 3: Main retry loop ────────────────────────────────────────────────

    while iteration < max_iterations:
        iteration += 1

        # Execute skills from the current plan
        for step in plan.steps:
            skill_input = SkillInput(
                task_id=task.task_id,
                step_id=step.step_id,
                skill_name=step.skill_name,
                payload=step.input,
                kg_context=kg_context,
                required_mcp_capabilities=list(
                    getattr(step, "required_mcp_capabilities", [])
                ),
                evidence_context=[
                    item.evidence_id for item in all_evidence_items
                ],
                metadata={
                    "iteration": iteration,
                    "expected_output": getattr(step, "expected_output", ""),
                    "evidence_requirements": list(
                        getattr(step, "evidence_requirements", [])
                    ),
                },
            )
            try:
                skill_output = skill_registry.run_skill(skill_input)
            except KeyError as exc:
                _record_skill_failure(
                    step=step,
                    iteration=iteration,
                    exc=exc,
                    skill_errors=skill_errors,
                    failed_steps=failed_steps,
                    warnings=warnings,
                )
                continue
            except Exception as exc:
                _record_skill_failure(
                    step=step,
                    iteration=iteration,
                    exc=exc,
                    skill_errors=skill_errors,
                    failed_steps=failed_steps,
                    warnings=warnings,
                )
                continue

            if skill_output is None:
                continue

            mcp_capability_audit.append(
                _build_mcp_audit_record(
                    skill_registry=skill_registry,
                    skill_input=skill_input,
                    skill_output=skill_output,
                )
            )

            if skill_output.warnings:
                warnings.extend(
                    f"{step.skill_name}: {warning}"
                    for warning in skill_output.warnings
                )

            if getattr(skill_output, "errors", None):
                _record_skill_output_errors(
                    step=step,
                    iteration=iteration,
                    skill_output=skill_output,
                    skill_errors=skill_errors,
                    failed_steps=failed_steps,
                    warnings=warnings,
                )
            elif getattr(skill_output, "status", "OK") == "FAILED":
                _record_skill_failure(
                    step=step,
                    iteration=iteration,
                    exc=RuntimeError("Skill returned FAILED without error detail"),
                    skill_errors=skill_errors,
                    failed_steps=failed_steps,
                    warnings=warnings,
                    error_type="SkillFailed",
                )

            if skill_output.artifacts:
                skill_artifacts.setdefault(step.step_id, []).append(
                    {
                        "iteration": iteration,
                        "skill_name": step.skill_name,
                        "artifacts": skill_output.artifacts,
                    }
                )
                if (
                    "skill_error" in skill_output.artifacts
                    and not getattr(skill_output, "errors", None)
                ):
                    _record_skill_failure(
                        step=step,
                        iteration=iteration,
                        exc=RuntimeError(str(skill_output.artifacts["skill_error"])),
                        skill_errors=skill_errors,
                        failed_steps=failed_steps,
                        warnings=warnings,
                        error_type=str(
                            skill_output.artifacts.get("error_type", "SkillError")
                        ),
                    )

            if skill_output.evidence_items:
                for item in skill_output.evidence_items:
                    if isinstance(item, EvidenceItem):
                        all_evidence_items.append(item)

        # Compile evidence graph from accumulated items
        compile_result = compile_evidence_graph(all_evidence_items)
        iteration_compile_reports.append(compile_result.report.to_dict())
        if compile_result.report.warnings:
            warnings.extend(compile_result.report.warnings)
        evidence_graph: EvidenceGraph = compile_result.graph

        # Critic review of current evidence
        critique = critic.review(
            task, evidence_graph, plan=plan, iteration=iteration
        )
        final_critique = critique

        # Check for PASS → exit successfully
        if critique.status == "PASS":
            break

        # Terminal statuses exit immediately.
        if critique.status in ("FAIL", "EXHAUSTED"):
            break

        # RETRY: use critic suggestions to re-plan
        if critique.retry_plan_suggestions:
            plan = planner.replan(task, kg, critique.retry_plan_suggestions)
        else:
            # No suggestions — increment iteration and try again
            plan = planner.replan(task, kg, list(critique.missing_evidence))

    # ── Step 4: Decision (only if we have evidence + critique result) ──────────

    final_compile_result: EvidenceGraphCompileResult = compile_evidence_graph(
        all_evidence_items
    )
    final_evidence_graph: EvidenceGraph = final_compile_result.graph
    if final_compile_result.report.warnings:
        warnings.extend(final_compile_result.report.warnings)

    if final_critique is None:
        # Safety: create a default FAIL critique if none was produced
        final_critique = CritiqueResult(status="FAIL", issues=["No critique generated"])
    elif final_critique.status == "RETRY" and iteration >= max_iterations:
        final_critique = CritiqueResult(
            status="EXHAUSTED",
            issues=["Retry budget exhausted: max_iterations reached"] + final_critique.issues,
            missing_evidence=final_critique.missing_evidence,
            retry_plan_suggestions=[],
            iteration=iteration,
        )

    try:
        final_decision = decision_engine.decide(
            task, final_evidence_graph, final_critique
        )
    except Exception as exc:
        warnings.append(f"DecisionEngine failed: {type(exc).__name__}: {exc}")
        final_decision = None

    # ── Step 5: Ledger ─────────────────────────────────────────────────────────

    if final_decision is not None:
        try:
            final_ledger = ledger_builder.build(
                final_decision, final_evidence_graph
            )
        except Exception as exc:
            warnings.append(f"LedgerBuilder failed: {type(exc).__name__}: {exc}")
            final_ledger = None

    # ── Step 6: Compile FinalThesis ────────────────────────────────────────────

    from src.schemas.report import FinalThesis
    artifacts: dict[str, Any] = {
        "skill_errors": skill_errors,
        "failed_steps": failed_steps,
        "warnings": warnings,
        "mcp_capability_audit": mcp_capability_audit,
        "skill_artifacts": skill_artifacts,
        "evidence_compile_report": final_compile_result.report.to_dict(),
        "iteration_compile_reports": iteration_compile_reports,
        "final_critique_status": final_critique.status,
        "final_decision_status": final_decision.action if final_decision else None,
        "ledger_id": final_ledger.ledger_id if final_ledger else None,
    }
    return FinalThesis(
        thesis_id=str(uuid.uuid4()),
        task_id=task.task_id,
        decision=(
            final_decision.to_dict()
            if final_decision is not None and hasattr(final_decision, "to_dict")
            else None
        ),
        ledger=(
            final_ledger.to_dict()
            if final_ledger is not None and hasattr(final_ledger, "to_dict")
            else None
        ),
        evidence_count=len(final_evidence_graph.items),
        iterations=iteration,
        critique_status=final_critique.status,
        circuit_broken=final_critique.status == "FAIL",
        kg_context_snapshot=kg_context,
        artifacts=artifacts,
        skill_errors=skill_errors,
        failed_steps=failed_steps,
        warnings=warnings,
        generated_at=datetime.now().isoformat(),
    )


# ── Internal helpers ───────────────────────────────────────────────────────────


def _query_kg_context(
    kg: KnowledgeGraph, task: ResearchTask, warnings: list[str] | None = None
) -> dict[str, Any]:
    """Query the Knowledge Graph for each fund in the task universe.

    This is called BEFORE Planner.plan() to enforce the KG-first constraint.
    For each fund code, retrieves the entity chain and exposure data.

    Args:
        kg:   KnowledgeGraph wrapper (may have graph=None).
        task: ResearchTask with fund_universe.

    Returns:
        Dict keyed by fund code, each containing ``chain`` and ``exposure``.
    """
    context: dict[str, Any] = {"fund_codes": list(task.fund_universe)}

    graph = getattr(kg, "graph", None)
    if graph is None:
        for code in task.fund_universe:
            context[code] = {"chain": {}, "exposure": {}}
        return context

    for code in task.fund_universe:
        fund_id = f"fund:{code}" if not code.startswith("fund:") else code
        try:
            chain = get_entity_chain(kg, fund_id, depth=2)
            exposure = query_exposure(kg, fund_id)
            context[code] = {"chain": chain, "exposure": exposure}
        except Exception as exc:
            if warnings is not None:
                warnings.append(
                    f"KG query failed for {fund_id}: {type(exc).__name__}: {exc}"
                )
            context[code] = {"chain": {}, "exposure": {}}

    return context


def _build_mcp_audit_record(
    *,
    skill_registry: SkillRegistry,
    skill_input: SkillInput,
    skill_output: Any,
) -> dict[str, Any]:
    """Build a JSON-safe MCP capability audit record for a skill step."""
    required = _required_capabilities_for_skill_input(skill_registry, skill_input)
    missing = [
        capability
        for capability in required
        if skill_registry.mcp_adapter is None
        or not skill_registry.mcp_adapter.has_capability(capability)
    ]
    return {
        "step_id": skill_input.step_id,
        "skill_name": skill_input.skill_name,
        "required_mcp_capabilities": required,
        "missing_mcp_capabilities": missing,
        "used_mcp_capabilities": list(
            getattr(skill_output, "used_mcp_capabilities", [])
        ),
        "status": getattr(skill_output, "status", "OK"),
    }


def _required_capabilities_for_skill_input(
    skill_registry: SkillRegistry,
    skill_input: SkillInput,
) -> list[str]:
    required = list(skill_input.required_mcp_capabilities)
    try:
        required.extend(skill_registry.get(skill_input.skill_name).required_mcp_capabilities)
    except KeyError:
        pass
    return list(dict.fromkeys(required))


def _record_skill_output_errors(
    *,
    step: Any,
    iteration: int,
    skill_output: Any,
    skill_errors: list[dict[str, Any]],
    failed_steps: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    """Record structured SkillOutput.errors in the runtime audit."""
    for error in getattr(skill_output, "errors", []):
        err_type = str(error.get("type", "SkillError"))
        message = str(error.get("message", "Skill failed"))
        skill_errors.append(
            {
                "iteration": iteration,
                "step_id": getattr(step, "step_id", ""),
                "skill_name": getattr(step, "skill_name", ""),
                "error_type": err_type,
                "message": message,
            }
        )
        failed_steps.append(
            {
                **(step.to_dict() if hasattr(step, "to_dict") else {}),
                "iteration": iteration,
                "error_type": err_type,
                "error": message,
            }
        )
        warnings.append(
            f"Skill {getattr(step, 'skill_name', '')} failed at iteration "
            f"{iteration}: {err_type}: {message}"
        )


def _record_skill_failure(
    *,
    step: Any,
    iteration: int,
    exc: Exception,
    skill_errors: list[dict[str, Any]],
    failed_steps: list[dict[str, Any]],
    warnings: list[str],
    error_type: str | None = None,
) -> None:
    """Record a failed skill step in the FinalThesis audit fields."""
    err_type = error_type or type(exc).__name__
    error = {
        "iteration": iteration,
        "step_id": getattr(step, "step_id", ""),
        "skill_name": getattr(step, "skill_name", ""),
        "error_type": err_type,
        "message": str(exc),
    }
    skill_errors.append(error)
    failed_steps.append(
        {
            **(step.to_dict() if hasattr(step, "to_dict") else {}),
            "iteration": iteration,
            "error_type": err_type,
            "error": str(exc),
        }
    )
    warnings.append(
        f"Skill {error['skill_name']} failed at iteration {iteration}: "
        f"{err_type}: {exc}"
    )
