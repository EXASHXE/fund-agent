# Decision Support Contract v1

**Version:** 1.0
**Contract ID:** `decision-support.v1`
**Runtime ID:** `decision_support`
**Markdown skill slug:** `decision-support`
**Machine-readable contract:** `skillpack/decision-contracts.yaml`

For the corresponding agent-facing skill instructions, see
[`skills/decision-support/SKILL.md`](../../skills/decision-support/SKILL.md).
For the formal decision schema, see
[`decision-contract.v2.md`](./decision-contract.v2.md).

This document defines the stable host-facing formal decision contract for
`DecisionSupportSkill`.

## Scope

`decision_support` consumes an already compiled `EvidenceGraph` from the host
or prior skill outputs. It applies deterministic local contract rules and may
emit formal `Decision` and `ExecutionLedger` artifacts.

`decision_support` does **not**:
- fetch data (NAV, holdings, news, sentiment, market, macro, or calendar)
- call provider SDKs (tavily, finnhub, exa, firecrawl, reddit, akshare, openai,
  anthropic, langchain)
- call LLMs
- perform brokerage or order execution
- import `src.skills_runtime.fund_analysis` or any other runtime skill

The **host** owns data fetching, provider SDKs, credentials, orchestration,
memory, retries, brokerage/order systems, and final UX.

## Input Modes

### Mode 1: `single_decision`

Build one formal `Decision` from an `EvidenceGraph` and optional action, budget,
and context fields.

**Required:**
- `payload.evidence_graph` — a compiled `EvidenceGraph` (dict with `items`,
  `edges`, optionally `stats`)

**Optional:**
- `payload.requested_action` — one of `BUY`, `SELL`, `INCREASE`, `REDUCE`,
  `WAIT`, `HOLD`, `PAUSE_DCA`
- `payload.target_trade_amount` — desired execution amount (float)
- `payload.portfolio_context` — dict with `total_value`, `cash_available`, etc.
- `payload.risk_profile` — dict with `risk_level`, `max_trade_pct`,
  `liquidity_reserve_pct`, `short_term_trade_budget_pct`
- `payload.constraints` — dict with `forbidden_actions`, `max_buy_amount`,
  `max_sell_amount`, `min_trade_amount`
- `payload.risk_budget` — dict with `risk_budget`, `max_trade_pct`
- `payload.time_horizon` — string, defaults to `"1 year"`
- `payload.critique` — dict with `status` (`PASS` / other) and `issues`
- `payload.deterministic` — boolean flag for stable test output (see below)

### Mode 2: `trade_plan_decision`

Validate and convert selected suggested trade plan entries into formal
`Decision` / `ExecutionLedger` artifacts.

**Required:**
- `payload.evidence_graph` — a compiled `EvidenceGraph`
- `payload.trade_plan.suggested_trade_plan[]` — list of trade entries, each
  with at least `trade_id`, `fund_code`, `action`

**Optional:**
- `payload.selected_trade_ids` — list of trade IDs to select; if empty, all
  trades are considered and the highest-priority one is selected
- `payload.portfolio_context`
- `payload.risk_profile`
- `payload.constraints`
- `payload.time_horizon`
- `payload.deterministic`

## Action Boundary

**Active actions** (require evidence anchors):
- `BUY` — initiate new position
- `SELL` — exit position
- `INCREASE` — add to position
- `REDUCE` — reduce position

**Passive actions** (may explain insufficient evidence or blockage):
- `WAIT` — defer decision
- `HOLD` — maintain current position
- `PAUSE_DCA` — pause dollar-cost averaging

**Policy:**
- Active actions **must** be anchored to evidence. Without at least one real
  evidence ID in the `EvidenceGraph`, the runtime downgrades active requests
  to `HOLD` / `WAIT` with structured blockage metadata.
- Passive actions can be produced when evidence is insufficient or constraints
  block active actions. They must explain why not buy/sell, what evidence is
  missing, what trigger would change the recommendation, and what invalidates
  the current stance.
- If host-provided `fund_analysis` artifacts are present, active requests are
  gatekept against fee risk, right-side confirmation, event hype failure,
  benchmark divergence, cash deployment readiness, and missing constraints.

## Structured Decision Justification

Formal `Decision` artifacts include structured justification metadata:

- `decision_reason_codes` — machine-readable reason codes. Current codes are
  `EVIDENCE_AVAILABLE`, `EVIDENCE_MISSING`, `EVIDENCE_STALE`,
  `EVIDENCE_WEAK`, `EVIDENCE_SUFFICIENT`, `EVIDENCE_CONTRADICTORY`,
  `INSUFFICIENT_EVIDENCE`, `CRITIC_BLOCKED`, `REDEMPTION_FEE_RISK`,
  `FEE_LOCKUP`, `THEME_OVERWEIGHT`, `RIGHT_SIDE_UNCONFIRMED`,
  `MOMENTUM_UNCONFIRMED`, `NEWS_NEGATIVE`, `NEWS_POSITIVE_BUT_PRICE_WEAK`,
  `BENCHMARK_DIVERGENCE`, `PROFIT_PROTECTION`, `LOSS_CONTROL`,
  `EVENT_HYPE_FAILED`, `CASH_BUFFER_LOW`, `CASH_DEPLOYMENT_NOT_READY`,
  `SHORT_TERM_BUDGET_EXCEEDED`, `TRANSACTION_HISTORY_MISSING`,
  `USER_CONSTRAINT_MISSING`, `VALUATION_UNKNOWN`, `CONSTRAINT_BLOCKED`,
  `BUDGET_BLOCKED`, `RISK_PROFILE_MISSING`, `LIQUIDITY_NEED_UNKNOWN`,
  `DOWNGRADED_ACTIVE_TO_HOLD`, `PASSIVE_ACTION`, and
  `ACTIVE_ACTION_ALLOWED`.
- `evidence_state` — one of `ANCHORED`, `INSUFFICIENT_EVIDENCE`,
  `CRITIC_BLOCKED`, `CONSTRAINT_BLOCKED`, `BUDGET_BLOCKED`, or `DOWNGRADED`.
- `blocked_by` — structured blocking causes such as `evidence`, `critic`,
  `constraint`, or `budget`.

Passive `WAIT` / `HOLD` / `PAUSE_DCA` decisions with an empty
`rationale_anchor` are valid only when `evidence_state` or
`decision_reason_codes` structurally explains insufficient evidence, critic
blockage, constraint blockage, budget blockage, or active-to-hold downgrade.
Legacy text-only explanation may be accepted for backward compatibility, but
new runtime outputs must populate the structured fields.

Active `BUY` / `SELL` / `INCREASE` / `REDUCE` decisions still require
`execution_amount > 0` and at least one real `rationale_anchor`. Structured
reason fields never replace real evidence anchors for active decisions.

When active actions are blocked by `fund_analysis` artifacts, the runtime
emits `HOLD` or `WAIT` using existing action semantics. No `WATCH`, `ADD`, or
`TRIM` formal action type is added; host-facing aliases map to the existing
`HOLD`, `INCREASE`, or `REDUCE` contract actions.

## Output Artifacts

The runtime may emit these artifact keys depending on the input mode:

| Key | Type | Produced When |
|---|---|---|
| `decision` | object | `single_decision` path produces one `Decision` |
| `decisions` | list | `trade_plan_decision` path produces one or more `Decision` objects |
| `execution_ledger` | object | One or more formal decisions are produced |
| `decision_status` | string | `single_decision` path; the selected formal action |
| `decision_count` | integer | `trade_plan_decision` path; number of formal decisions emitted |
| `audit_trail` | list | Decision artifacts include audit data |
| `warnings` | list | Validation/capping/skipping warnings are emitted |
| `evidence_anchor_diagnostics` | object | Formal decision is produced; explains anchor validity/coverage per decision and per trade |
| `risk_constraint_conflicts` | object | Constraints or budget block an active action; explains budget/constraint blocking with cap/downgrade details |

## Formal Decision Boundary

- **Only `decision_support` may emit formal `Decision` / `ExecutionLedger`**
  artifacts.
- `fund_analysis` MUST NOT emit formal `Decision` or `ExecutionLedger`.
- `fund_analysis` `suggested_rebalance_plan` is a suggested analysis plan, not
  an order, not a formal decision, and not a broker instruction.
- `decision_support` does not execute trades, does not place orders, and does
  not connect to brokerage systems.
- `execution_ledger` now includes a `ledger_summary` field providing a
  deterministic summary of all decisions, total execution amounts, and
  passive/active action counts within the ledger.

## Risk and Trade Amount Policy

- `constraints.forbidden_actions` must be respected; forbidden actions are
  skipped with warnings.
- `risk_profile` / `risk_budget` / `portfolio_context` may cap trade amounts
  (max trade percentage, cash available, max buy/sell amount, short-term budget).
- Zero or invalid active trade amount leads to downgrade/rejection according to
  current runtime behavior.
- `selected_trade_ids` filters trade plan entries where supported.
- `decision_support` does not execute trades.

## Auditability

- Outputs carry `rationale_anchor` when evidence is available.
- Outputs carry `trigger_conditions` (conditions that would permit or change
  action) and `invalidating_conditions` (conditions that would invalidate this
  decision).
- Outputs carry `audit_trail` with evidence item counts, critique status,
  execution amount reasoning, downgrade reasons, and generation timestamps.
- Deterministic test mode (`payload.deterministic: true`) may produce stable
  `decision_id` (SHA256 hash of stable fields) and `created_at` (from
  `as_of_date`) when currently supported by runtime.

## Status Semantics

| Status | Meaning |
|---|---|
| `OK` | Decision or execution ledger produced successfully. |
| `PARTIAL` | No suitable trades or decisions after validation, but the bridge command succeeded. A `WAIT` / passive decision or empty trade result was emitted. |
| `FAILED` | Input contract violation (e.g. missing `payload.evidence_graph`) or runtime error. |

## Cross-References

- [`skill-output-contract.v1.md`](./skill-output-contract.v1.md)
- [`fund-analysis-artifacts.v1.md`](./fund-analysis-artifacts.v1.md)
- [`fund-analysis-input-contract.v1.md`](./fund-analysis-input-contract.v1.md)
- [`report-output-contract.v1.md`](./report-output-contract.v1.md)
- [`decision-contract.v2.md`](./decision-contract.v2.md)
- [`skillpack/decision-contracts.yaml`](../../skillpack/decision-contracts.yaml)
- [`skills/decision-support/SKILL.md`](../../skills/decision-support/SKILL.md)
