---
id: decision_support
name: decision-support
description: "Supporting skill. The only fund-agent skill that may produce a formal Decision and ExecutionLedger. Consumes an EvidenceGraph plus optional portfolio context, risk profile, constraints, and target trade amount. Active actions require evidence anchors."
runtime: src.skills_runtime.decision_support:DecisionSupportSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
consumes:
  - EvidenceGraph
produces:
  - Decision
  - ExecutionLedger
role: supporting
---

# Decision Support (supporting skill)

`decision-support` is a **supporting skill** in the
`fund-agent` Superpowers-compatible skill collection. It must be
loaded only when the user is asking for a formal trade / action
decision, and only after an `EvidenceGraph` (and optional trade plan)
exists. For ordinary portfolio and fund report requests, start with
the primary skill `fund-analysis` and stop there.

`decision-support` is the **only** skill that may produce a formal
`Decision` or `ExecutionLedger`. No other skill — including
`fund-analysis`, `news-research`, `sentiment-analysis`, or
`thesis-generation` — may produce these artifacts.

`decision-support` itself maps to the Python runtime ID
`decision_support` declared in
`skillpack/fund-agent.skillpack.yaml`. The agent-facing skill name is
the hyphenated slug `decision-support`; the underscore
`decision_support` is the runtime ID only.

## Purpose

Use `decision_support` to turn a compiled `EvidenceGraph` and optional trade
plan into formal, contract-enforced `Decision` and `ExecutionLedger` artifacts.
This is the only skill allowed to emit `Decision` or `ExecutionLedger`.

## When to use this skill

- The user asks for actionable trade advice.
- The host needs a formal BUY, SELL, INCREASE, REDUCE, WAIT, HOLD, or PAUSE_DCA
  decision.
- The host has already compiled evidence with `compile_evidence_graph`.
- The host wants a deterministic decision audit trail.
- A `fund_analysis` `suggested_rebalance_plan` needs formal validation.

**`decision-support` is not for ordinary report-only requests.** A user
asking `分析下我的基金给出报告` should be served by `fund-analysis`
alone. Only escalate to `decision-support` when the user asks for an
actionable trade decision.

## When not to use this skill

- Do not call it before evidence has been gathered and compiled.
- Do not use it for an ordinary portfolio report. Use `fund-analysis`.
- Do not use it to fetch news, market data, holdings, NAV, or sentiment.
- Do not use it to create a thesis draft without formal decision intent.
  Use `thesis-generation` for a draft thesis.
- Do not use it as a planner, autonomous loop, or provider integration.

## Host responsibilities

The host owns data fetching, evidence collection, EvidenceGraph compilation,
trade plan selection, user suitability checks, final UX, and whether formal
decisions are appropriate. The host must provide `evidence_graph` and any
portfolio context, risk profile, constraints, selected trade IDs, and
deterministic mode options in `SkillInput.payload`.

## Inputs

Runtime skill ID: `decision_support`.
Runtime: `src.skills_runtime.decision_support:DecisionSupportSkill`.
MCP capabilities required: none.

Required:

- `payload.evidence_graph`
- `payload.objective` or equivalent host task context

Optional:

- `payload.trade_plan`
- `payload.selected_trade_ids`
- `payload.portfolio_context`
- `payload.risk_profile`
- `payload.constraints`
- `payload.target_trade_amount`
- `payload.time_horizon`
- `payload.requested_action`
- `payload.deterministic`

## Outputs

- `decision`
- `decisions`
- `execution_ledger`
- `decision_status`
- `decision_count`
- `audit_trail`
- `warnings`
- `errors`

Output shape depends on whether the host provides one general decision request
or a multi-leg trade plan.

## EvidenceGraph requirements

Active decisions require evidence anchors that are real IDs inside the supplied
`EvidenceGraph`. Arbitrary first-N evidence IDs are not sufficient. Anchors must
be relevant to the action, fund, trade, or risk flag being decided.

## Trade plan requirements

Trade plans should preserve `trade_id`, `fund_code`, `action`, `amount` or
`requested_amount`, rationale, and trade-specific `evidence_refs` or
`risk_flags_refs`. For active BUY, SELL, INCREASE, or REDUCE actions, those refs
must resolve to evidence IDs in the `EvidenceGraph`.

## Active decision evidence-anchor policy

Active BUY, SELL, INCREASE, and REDUCE decisions require trade-specific evidence
refs. Missing, unrelated, or fake refs must downgrade to WAIT or HOLD. A broad
portfolio evidence list cannot justify an active trade unless the referenced
evidence actually supports that trade.

Active evidence anchors must be explicit, real, and trade-specific.

See `references/evidence-anchor-policy.md`.

## WAIT/HOLD policy

WAIT and HOLD are valid only when explained. A WAIT/HOLD rationale must state:

- why not buy;
- why not sell;
- what evidence is missing;
- what trigger would change the recommendation;
- what invalidates the current stance.

WAIT/HOLD must not be filler for weak reasoning.

See `references/wait-hold-policy.md`.

## Deterministic mode policy

When `deterministic=true`, `decision_id`, `created_at`, and audit trail timing
must be stable for the same payload. Runtime nondeterministic IDs and timestamps
are allowed only when `deterministic=false` or omitted.

See `references/deterministic-mode.md`.

## Risk budget policy

Risk budget must come from host-provided portfolio context, risk profile,
constraints, and time horizon. If the payload does not support a safe active
risk budget, return WAIT or HOLD with an audit note.

## Execution amount capping policy

Execution amounts must respect cash, current position value, max trade
percentage, max buy or sell amount, short-term budget where applicable, minimum
trade amount, forbidden actions, and requested amount. Invalid or unsafe active
amounts must be capped or downgraded.

See `references/execution-amount-policy.md`.

## Trigger conditions policy

Every decision should include concrete trigger conditions that would permit or
change action. Passive decisions should name the missing evidence or threshold
needed to move from WAIT/HOLD to active action.

## Invalidating conditions policy

Every decision should include invalidating conditions such as evidence
contradiction, risk budget breach, market regime change, portfolio cash change,
or trade-specific thesis failure.

## ExecutionLedger policy

Every formal decision output must be recorded in an `ExecutionLedger`. The
ledger should preserve decision IDs, actions, execution amounts, evidence IDs,
audit trail, version, and timestamps according to the decision contract.

## Forbidden behavior

This skill must never:

- make direct network calls;
- import provider SDKs;
- call LLMs;
- fabricate evidence anchors;
- use arbitrary first-N evidence IDs as active trade support;
- emit active decisions without trade-specific evidence refs;
- fetch or infer market data;
- allow any other skill to emit formal `Decision` or `ExecutionLedger`.

## Active decision evidence-anchor policy (re-stated)

Active BUY, SELL, INCREASE, and REDUCE decisions must be anchored to
trade-specific evidence IDs in the supplied `EvidenceGraph`. A broad
portfolio evidence list cannot justify an active trade unless the
referenced evidence actually supports that trade.

## Examples

### Minimal invocation

```json
{
  "task_id": "task-1",
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "payload": {
    "evidence_graph": {"items": {}, "edges": []},
    "objective": "review fund",
    "risk_budget": {},
    "portfolio_context": {},
    "time_horizon": "1 year"
  },
  "required_mcp_capabilities": []
}
```

### Minimal output

```json
{
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "evidence_items": [],
  "artifacts": {
    "decision": {},
    "execution_ledger": {},
    "decision_status": "WAIT",
    "audit_trail": ["Insufficient evidence"]
  },
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "status": "OK"
}
```

More examples are in `references/examples.md` and the formal contract is in
`references/decision-contract.md`.

## References

- `references/evidence-anchor-policy.md`
- `references/wait-hold-policy.md`
- `references/execution-amount-policy.md`
- `references/deterministic-mode.md`
- `references/decision-contract.md`
- `references/examples.md`
