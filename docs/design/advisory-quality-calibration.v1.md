# Advisory Quality Calibration — v1.5

**Status:** implemented
**Sections:** A-I (full advisory quality calibration)

---

## 1. Advisory Intent Taxonomy

`src/skills_runtime/workflow/advisory_intent.py` provides a deterministic,
LLM-free intent classifier using explicit host-provided fields and keyword
matching.

### Supported Intents

| Intent | Trigger |
|--------|---------|
| `REPORT_ONLY` | 分析/报告/怎么看 without action keywords |
| `FORMAL_TRADE_DECISION` | 买/卖/减仓/加仓/正式决策 |
| `PROFIT_PROTECTION` | 盈利很多/本金回收/止盈/落袋 |
| `DRAWDOWN_RESPONSE` | 跌了很多/回撤/要不要补/要不要割 |
| `RIGHT_SIDE_CONFIRMATION` | 右侧/企稳/反弹确认 |
| `SHORT_HOLDING_FEE_CHECK` | 7天/手续费/赎回费 |
| `CASH_DEPLOYMENT` | 现金/债券仓位/余额宝/部署/还能投哪 |
| `OVERLAP_CONCENTRATION_CHECK` | 重合/持仓重复/QDII/AI/美股科技 |
| `DCA_REVIEW` | 定投/DCA |
| `RISK_REDUCTION` | 风险太大/降风险/保守 |
| `PORTFOLIO_REBALANCE` | 调整仓位/配置/平衡 |
| `WATCHLIST_ONLY` | 观察/关注/跟踪 |

### Rules
- `FORMAL_TRADE_DECISION` is ONLY set when user explicitly requests buy/sell/reduce.
- Default fallback is `REPORT_ONLY`.
- Classification is exposed in workflow_summary.advisory_intents.
- `is_report_only()` and `is_formal_decision_requested()` helpers available.

---

## 2. Final Workflow Report Quality (v1.5)

### New Sections

The final report now includes 8 user-facing sections instead of 4:

1. **direct_answer** — 2-5 bullet answer to the user's actual question.
   Examples:
   - "Formal decision was evaluated and blocked: evidence, right_side_unconfirmed."
   - "This is an analysis/report-only scenario. No formal trade decision evaluated."
   - "Short-holding redemption fee risk is prominent."

2. **evidence_status** (enhanced) — Data sufficiency with levels:
   - `[sufficient]` — Available evidence counts
   - `[missing]` — Missing evidence gaps
   - `[blocker]` — Active blockers from decision_support
   - `[warning]` — Non-blocking warnings

3. **portfolio_diagnosis** — Portfolio-level issues:
   - Concentration / overlap
   - Cash / bond deployment readiness
   - Profit protection alerts
   - Right-side confirmation status
   - Redemption fee blockers
   - PnL summary

4. **summary** — (was section 1, now section 4) Workflow metadata.

5. **decision_explanation** — (was section 3) Formal decision detail.

6. **action_boundary** — Clear separation between analysis-only and formal:
   - "fund-agent does not execute broker orders."
   - "Formal decision was produced by decision_support (only authorized producer)."
   - "Host must not convert analysis-only suggestions into broker orders."

7. **recommended_next_steps** — Safe next actions:
   - Fetch missing data
   - Wait for confirmation signals
   - Resolve blockers
   - Use decision_support for formal decisions

8. **limitations** — (was section 4) Quality grade, warnings.

### Chinese Support (zh-CN)

When `language="zh-CN"`, the report includes a `chinese_summary` section with
natural Chinese bullets suitable for direct user display:
- Portfolio overview in Chinese
- Decision status translated
- Evidence availability in Chinese
- Fee/redemption risk explained
- Right-side confirmation guidance
- Profit protection suggestions
- Cash deployment analysis
- Safety disclaimer

### Key Principles

- Do not fabricate missing data.
- Do not produce broker/order execution.
- Do not create formal decisions without decision_support.
- Keep deterministic output.
- Reuse existing artifacts.
- No LLM calls.

---

## 3. fund_analysis Business Coherence

### Profit Protection
- Distinguishes "recover principal", "free carry", "trim pressure".
- Does NOT recommend full exit solely because profit is high.
- Suggested trim is analysis-only unless decision_support confirms.
- If transaction history is missing, marks principal recovery as unknown.

### Drawdown / Right-Side Confirmation
- Distinguishes falling knife vs confirmed rebound.
- Active BUY/INCREASE requires benchmark/news/sentiment/NAV confirmation.
- If evidence missing, reports "观察/等确认" rather than "补仓".

### Short-Holding Fee Risk
- Fee/redemption warning prominent in report and Chinese summary.
- Suggested SELL is blocked/downgraded.
- Direct answer explains fee risk.

### Overlap / Concentration
- Report explains overlap at fund/holding/theme level.
- Knowledge graph summary supports overlap analysis.
- If holdings insufficient, explicitly states "cannot assess".

### Cash / Bond Deployment
- Separates liquidity reserve from deployable cash.
- Does not imply all cash can be invested.
- Respects risk_profile and constraints.

### Risk Profile Sensitivity
- Conservative: prefers HOLD/WAIT, lower trade caps, stronger blockers.
- Aggressive: may allow higher risk budget but still requires anchors.
- Balanced: uses default caps.

---

## 4. decision_support Advisory Quality

### Reason Codes
Stable reason codes for:
- `EVIDENCE_MISSING`, `INSUFFICIENT_EVIDENCE`
- `RIGHT_SIDE_UNCONFIRMED`
- `REDEMPTION_FEE_RISK`, `FEE_LOCKUP`
- `BUDGET_BLOCKED`, `CONSTRAINT_BLOCKED`
- `PROFIT_PROTECTION`
- `BENCHMARK_DIVERGENCE`
- `CASH_DEPLOYMENT_NOT_READY`
- `DOWNGRADED_ACTIVE_TO_HOLD`, `PASSIVE_ACTION`
- `ACTIVE_ACTION_ALLOWED`

### Requested vs Final Action
- Every formal decision preserves requested_action and final action.
- Blocked/downgraded reason is explicit in blocked_by and reason_codes.

### Passive Safety Decisions
- If active action is blocked, produces HOLD/WAIT with clear rationale.
- Does not imply execution.
- User-facing reason text in audit trail.

---

## 5. Chinese E2E Fixtures (v1.5)

New fixtures added under `examples/e2e_advisory_workflows/`:

| Fixture | Intent | Key Assertions |
|---------|--------|---------------|
| `semiconductor_profit_recover_principal_zh` | PROFIT_PROTECTION + FORMAL_TRADE_DECISION | Partial REDUCE, no full liquidation, Chinese direct_answer |
| `innovation_drug_7day_drawdown_wait_for_confirmation_zh` | DRAWDOWN_RESPONSE + RIGHT_SIDE_CONFIRMATION | BUY blocked, wait/watch guidance |
| `short_holding_fee_sell_zh` | SHORT_HOLDING_FEE_CHECK + FORMAL_TRADE_DECISION | SELL blocked, redemption fee prominent |
| `qdii_ai_overlap_report_zh` | REPORT_ONLY + OVERLAP_CONCENTRATION_CHECK | No decision_support, holdings overlap analysis |
| `cash_bond_where_to_deploy_zh` | CASH_DEPLOYMENT | Separates reserve vs deployable, no product recommendation |
| `conservative_vs_aggressive_same_portfolio` | FORMAL_TRADE_DECISION | Decision posture differs by risk profile |

---

## 6. E2E Test Coverage (v1.5)

New test classes:

| Class | Tests |
|-------|-------|
| `TestDirectAnswer` | All reports have direct_answer section |
| `TestChineseScenarios` | chinese_summary exists, zh report-only no DS call, fee mentioned, BUY blocked, profit partial, cash reserve, overlap analysis |
| `TestRiskProfileCalibration` | conservative_vs_aggressive produces formal evaluation, passive posture expected |
| `TestNoBrokerExecutionFields` | No execution fields in all v1.5 reports + Chinese summary |
| `TestWorkflowSummaryIntents` | advisory_intents present in workflow_summary |

---

## 7. Non-Goals (Not Done)

- No install/plugin/deployment changes.
- No network/provider SDK/broker execution.
- No LLM calls inside runtime.
- No new provider SDKs.
- No broker/order execution.
- fund_analysis still never emits formal Decision/ExecutionLedger.
- decision_support remains the only formal decision producer.
