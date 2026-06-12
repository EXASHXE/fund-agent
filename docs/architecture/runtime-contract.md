# Optional Research OS Reference Contract

This document describes an optional reference workflow retained for
compatibility and examples. It is not the host integration contract and not a
required entrypoint for the fund-agent skill pack. External agents should use
`skillpack/fund-agent.skillpack.yaml` and `src/skills_runtime` directly.

## Runtime Flow

`ResearchTask -> Planner -> KG -> SkillInput -> SkillRegistry -> SkillOutput -> EvidenceGraph -> Critic -> DecisionEngine -> Ledger`

1. `ResearchTask` enters through the host-supplied orchestration layer
   (see `v0.1.0-skillpack-alpha` tag for the historical `research_os` wrapper).
2. `Planner` builds ordered skill steps from task and KnowledgeGraph context.
3. KG queries run before planning context is used. Query failures fall back to
   empty context and must be recorded as warnings.
4. The **host** converts each `PlanStep` to `SkillInput`. (Historical: see `v0.1.0-skillpack-alpha` tag for the `research_os` wrapper.)
5. `SkillRegistry` executes skill handlers with an injected `MCPHostAdapter`.
   Missing skills, missing MCP capabilities, and skill failures are recorded in
   runtime audit fields.
6. `compile_evidence_graph` validates evidence, rejects invalid items,
   deduplicates, detects conflicts, upgrades corroborated soft evidence, and
   aggregates confidence.
7. `Critic` reviews the compiled graph. If blocking issues remain after retry
   budget exhaustion, the status is `EXHAUSTED`.
8. `DecisionEngine` creates a contract-enforced passive or active decision.
9. `LedgerBuilder` wraps the decision in an `ExecutionLedger`.

## Runtime Audit Fields

`FinalThesis.artifacts` must include:

- `skill_errors`
- `failed_steps`
- `warnings`
- `mcp_capability_audit`
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

Passive decisions may use an empty `rationale_anchor` only when structured
`decision_reason_codes` or `evidence_state` explain insufficient evidence,
critic blockage, constraint blockage, budget blockage, or active-to-hold
downgrade. Legacy text-only explanations are compatibility-only and are not
sufficient for new runtime outputs.

`ExecutionLedger.to_dict()` includes `ledger_id`, decision IDs, `evidence_ids`,
`audit_trail`, structured justification fields, and `created_at`.

## MCP Host Adapter Boundary

`src.tools.adapters.mcp` declares host-native MCP capabilities:

- `MCPCapability`
- `MCPHostAdapter`
- `InMemoryMCPHostAdapter`

The adapter layer is a declaration/call boundary only. It must not import
provider SDKs, perform network IO, or embed Tavily/Finnhub/Exa/Firecrawl/Reddit
calls. Providers are injected by the host runtime.
