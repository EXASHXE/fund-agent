"""Research OS — main orchestration loop for AI Financial Research.

The ResearchOS loop is the primary integration point that orchestrates the
full fund-research pipeline:

    1. KG query (MUST happen before Planner, enforced here)
    2. Plan generation (Planner receives KG context)
    3. Skill execution (registered skills produce EvidenceItems)
    4. Evidence compilation (compile_evidence_graph)
    5. Critic review (structural checks → PASS / RETRY / FAIL)
    6. Decision generation (DecisionEngine.enforce contract rules)
    7. Ledger construction (LedgerBuilder → ExecutionLedger)

Constraints:
    - Max 3 retries by default (configurable via max_iterations)
    - Circuit breaker on FAIL critique — exits the loop immediately
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
from src.tools.evidence.validators import compile_evidence_graph


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

    # ── Step 1: Query KG FIRST (before anything else) ──────────────────────────
    # Enforced: KG context MUST be captured before Planner.plan() is called.
    kg_context: dict[str, Any] = _query_kg_context(kg, task)

    # ── Step 2: Generate initial plan (Planner also queries KG internally) ─────
    plan = planner.plan(task, kg)
    plan.kg_context_snapshot = kg_context

    # ── Step 3: Main retry loop ────────────────────────────────────────────────

    while iteration < max_iterations:
        iteration += 1

        # Execute skills from the current plan
        for step in plan.steps:
            try:
                skill_output = skill_registry.run(step.skill_name, step.input)
                if skill_output is not None and skill_output.evidence_items:
                    for item in skill_output.evidence_items:
                        if isinstance(item, EvidenceItem):
                            all_evidence_items.append(item)
            except (KeyError, Exception):
                # Skill not registered or execution failed — skip
                pass

        # Compile evidence graph from accumulated items
        evidence_graph: EvidenceGraph
        if all_evidence_items:
            evidence_graph = compile_evidence_graph(all_evidence_items)
        else:
            evidence_graph = EvidenceGraph()

        # Critic review of current evidence
        critique = critic.review(
            task, evidence_graph, plan=plan, iteration=iteration
        )
        final_critique = critique

        # Check for PASS → exit successfully
        if critique.status == "PASS":
            break

        # Circuit breaker: FAIL → exit immediately
        if critique.status == "FAIL":
            break

        # RETRY: use critic suggestions to re-plan
        if critique.retry_plan_suggestions:
            plan = planner.replan(task, kg, critique.retry_plan_suggestions)
        else:
            # No suggestions — increment iteration and try again
            plan = planner.replan(task, kg, list(critique.missing_evidence))

    # ── Step 4: Decision (only if we have evidence + critique result) ──────────

    final_evidence_graph: EvidenceGraph
    if all_evidence_items:
        final_evidence_graph = compile_evidence_graph(all_evidence_items)
    else:
        final_evidence_graph = EvidenceGraph()

    if final_critique is None:
        # Safety: create a default FAIL critique if none was produced
        final_critique = CritiqueResult(status="FAIL", issues=["No critique generated"])

    try:
        final_decision = decision_engine.decide(
            task, final_evidence_graph, final_critique
        )
    except Exception:
        final_decision = None

    # ── Step 5: Ledger ─────────────────────────────────────────────────────────

    if final_decision is not None:
        try:
            final_ledger = ledger_builder.build(
                final_decision, final_evidence_graph
            )
        except Exception:
            final_ledger = None

    # ── Step 6: Compile FinalThesis ────────────────────────────────────────────

    from src.schemas.report import FinalThesis
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
        evidence_count=len(all_evidence_items),
        iterations=iteration,
        critique_status=final_critique.status,
        circuit_broken=final_critique.status == "FAIL",
        kg_context_snapshot=kg_context,
        generated_at=datetime.now().isoformat(),
    )


# ── Internal helpers ───────────────────────────────────────────────────────────


def _query_kg_context(
    kg: KnowledgeGraph, task: ResearchTask
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
        except Exception:
            context[code] = {"chain": {}, "exposure": {}}

    return context
