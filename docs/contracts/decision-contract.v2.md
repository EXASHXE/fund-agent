# Decision Contract v2

## Decision Schema

`src/schemas/decision.py`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision_id` | `str` | Yes | Unique identifier |
| `action` | `ActionType` | Yes | `BUY`, `SELL`, `HOLD`, `PAUSE_DCA`, `REDUCE`, `INCREASE`, or `WAIT` |
| `execution_amount` | `float` | Yes | Must be > 0 for BUY/SELL/INCREASE/REDUCE |
| `rationale_anchor` | `list[str]` | Yes | Evidence IDs; active actions must have at least 1 real evidence ID |
| `trigger_conditions` | `list[str]` | Yes | Conditions that trigger this decision |
| `invalidating_conditions` | `list[str]` | Yes | Conditions that invalidate this decision |
| `time_horizon` | `str` | Yes | Expected time horizon |
| `risk_budget` | `float` | Yes | Must be > 0 |
| `audit_trail` | `list[str]` | No | Evidence ID chain for traceability |
| `decision_reason_codes` | `list[str]` | No | Machine-readable justification codes |
| `evidence_state` | `str` | No | Structured evidence/blockage state |
| `blocked_by` | `list[str]` | No | Structured blocking causes |
| `version` | `str` | Yes | `"decision-contract.v2"` |
| `created_at` | `datetime` | Yes | When generated |

## Allowed Actions

| Action | Description | Execution Amount |
|--------|-------------|-----------------|
| `BUY` | Initiate new position | Required, > 0 |
| `SELL` | Exit position | Required, > 0 |
| `INCREASE` | Add to position | Required, > 0 |
| `REDUCE` | Reduce position | Required, > 0 |
| `HOLD` | Maintain current position | Not required (any value) |
| `WAIT` | Defer decision | Not required (any value) |
| `PAUSE_DCA` | Pause dollar-cost averaging | Not required (any value) |

## Required Fields Validation

All fields are validated at construction time via `__post_init__`. A Decision is invalid if:

| Condition | Error |
|-----------|-------|
| Missing `trigger_conditions` | `ValueError("Decision must specify trigger_conditions")` |
| Missing `invalidating_conditions` | `ValueError("Decision must specify invalidating_conditions")` |
| Empty `rationale_anchor` for active action | `ValueError("Active decision must reference at least one evidence_id in rationale_anchor")` |
| Empty `rationale_anchor` for passive action without structured justification | `ValueError("WAIT/HOLD/PAUSE_DCA with empty rationale_anchor must carry structured decision_reason_codes or evidence_state...")` |
| `execution_amount <= 0` for BUY/SELL/INCREASE/REDUCE | `ValueError("Action '{action}' requires execution_amount > 0, got {amount}")` |
| `risk_budget <= 0` | `ValueError("risk_budget must be > 0, got {amount}")` |

## Evidence Anchoring Rules

1. Active decisions must reference `rationale_anchor` from `EvidenceGraph` evidence IDs.
2. No evidence → no active action (only WAIT/HOLD/PAUSE_DCA allowed without evidence).
3. CritiqueResult must be PASS for BUY/SELL/INCREASE/REDUCE.
4. Passive decisions with an empty `rationale_anchor` must carry structured
   `decision_reason_codes` or `evidence_state` explaining insufficient
   evidence, critic blockage, constraint blockage, budget blockage, or
   active-to-hold downgrade.
5. Structured reason fields do not replace real evidence anchors for active
   decisions.

## Structured Justification Fields

Allowed `decision_reason_codes`:

- `EVIDENCE_AVAILABLE`
- `EVIDENCE_MISSING`
- `EVIDENCE_STALE`
- `EVIDENCE_WEAK`
- `EVIDENCE_SUFFICIENT`
- `EVIDENCE_CONTRADICTORY`
- `INSUFFICIENT_EVIDENCE`
- `CRITIC_BLOCKED`
- `REDEMPTION_FEE_RISK`
- `FEE_LOCKUP`
- `THEME_OVERWEIGHT`
- `RIGHT_SIDE_UNCONFIRMED`
- `MOMENTUM_UNCONFIRMED`
- `NEWS_NEGATIVE`
- `NEWS_POSITIVE_BUT_PRICE_WEAK`
- `BENCHMARK_DIVERGENCE`
- `PROFIT_PROTECTION`
- `LOSS_CONTROL`
- `EVENT_HYPE_FAILED`
- `CASH_BUFFER_LOW`
- `CASH_DEPLOYMENT_NOT_READY`
- `SHORT_TERM_BUDGET_EXCEEDED`
- `TRANSACTION_HISTORY_MISSING`
- `USER_CONSTRAINT_MISSING`
- `VALUATION_UNKNOWN`
- `CONSTRAINT_BLOCKED`
- `BUDGET_BLOCKED`
- `RISK_PROFILE_MISSING`
- `LIQUIDITY_NEED_UNKNOWN`
- `DOWNGRADED_ACTIVE_TO_HOLD`
- `PASSIVE_ACTION`
- `ACTIVE_ACTION_ALLOWED`

Allowed `evidence_state` values:

- `ANCHORED`
- `INSUFFICIENT_EVIDENCE`
- `CRITIC_BLOCKED`
- `CONSTRAINT_BLOCKED`
- `BUDGET_BLOCKED`
- `DOWNGRADED`

## Risk Budget Rules

1. Risk budget varies by risk_profile: conservative = 0.02, moderate = 0.05, aggressive = 0.10.
2. Active actions (BUY/SELL/INCREASE/REDUCE) use full risk budget; passive actions (HOLD/WAIT/PAUSE_DCA) use 0.01.
3. Risk budget must be > 0 (enforced).

## Trigger and Invalidating Condition Rules

1. `trigger_conditions` — what must be true for this decision to execute.
2. `invalidating_conditions` — what would make this decision wrong.
3. Common conditions to include: evidence contradiction detection, CRISIS regime, risk budget exceeded, time horizon elapsed.

## ExecutionLedger Schema

`src/schemas/decision.py`

| Field | Type | Description |
|-------|------|-------------|
| `decisions` | `list[Decision]` | All decisions in the ledger |
| `generated_at` | `datetime` | When the ledger was generated |
| `version` | `str` | `"execution-ledger.v1"` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialization with timestamp formatting |
| `total_risk_budget()` | `float` | Sum of all risk budgets across decisions |
| `actions_summary()` | `dict[str, int]` | Count of each action type |
