# Research OS Runtime Contract

This document describes the beta Research OS runtime contract. It is a contract
and boundary statement, not a production-readiness claim.

## Runtime Flow

`ResearchTask -> Planner -> KG -> Skill -> EvidenceGraph -> Critic -> DecisionEngine -> Ledger`

1. `ResearchTask` enters through `src.core.research_os.run_research_task` or
   the thin `src.workflows.research_os` wrapper.
2. `Planner` builds ordered skill steps from task and KnowledgeGraph context.
3. KG queries run before planning context is used. Query failures fall back to
   empty context and must be recorded as warnings.
4. `SkillRegistry` executes skill handlers. Missing skills and skill failures
   are recorded in runtime audit fields.
5. `compile_evidence_graph` validates evidence, rejects invalid items,
   deduplicates, detects conflicts, upgrades corroborated soft evidence, and
   aggregates confidence.
6. `Critic` reviews the compiled graph. If blocking issues remain after retry
   budget exhaustion, the status is `EXHAUSTED`.
7. `DecisionEngine` creates a contract-enforced passive or active decision.
8. `LedgerBuilder` wraps the decision in an `ExecutionLedger`.

## Runtime Audit Fields

`FinalThesis.artifacts` must include:

- `skill_errors`
- `failed_steps`
- `warnings`
- `evidence_compile_report`
- `iteration_compile_reports`
- `final_critique_status`
- `final_decision_status`
- `ledger_id`

`FinalThesis.to_dict()` must be JSON serializable.

## Critic EXHAUSTED

`EXHAUSTED` means retry budget was spent and blocking issues still exist. It is
not a successful review. A Research OS run with `EXHAUSTED` must not produce
active actions (`BUY`, `SELL`, `INCREASE`, `REDUCE`). Only passive actions
(`WAIT`, `HOLD`, `PAUSE_DCA`) are allowed.

## EvidenceGraph Compile Contract

`compile_evidence_graph(items)` returns:

```python
EvidenceGraphCompileResult(
    graph=EvidenceGraph(...),
    report=EvidenceGraphCompileReport(...),
)
```

The report includes:

- `accepted_count`
- `rejected_count`
- `rejected_items`
- `deduplicated_count`
- `conflict_count`
- `hybrid_upgraded_count`
- `confidence_by_entity`
- `average_confidence`
- `warnings`

Invalid evidence is rejected when required fields are missing or when
`HardEvidence.confidence_weight != 1.0`. Soft evidence is upgraded to hybrid
only when independent sources corroborate the same entity and direction.
`EvidenceGraph.to_dict()` is pure read and must not mutate edges.

## Decision Anchor Contract

Active decisions must anchor to real `EvidenceGraph` evidence IDs. Fake anchors
such as `no_evidence_available`, `fake_anchor`, or `placeholder` are invalid.

Passive decisions may use an empty `rationale_anchor` only when the audit trail
or trigger conditions explain insufficient evidence, critic blockage, or
exhaustion.

`ExecutionLedger.to_dict()` includes `ledger_id`, decision IDs, `evidence_ids`,
`audit_trail`, and `created_at`.

## MCP Host Adapter Boundary

`src.tools.adapters.mcp` declares host-native MCP capabilities:

- `MCPCapability`
- `MCPHostAdapter`
- `InMemoryMCPHostAdapter`

The adapter layer is a declaration/call boundary only. It must not import
provider SDKs, perform network IO, or embed Tavily/Finnhub/Exa/Firecrawl/Reddit
calls. Providers are injected by the host runtime.
