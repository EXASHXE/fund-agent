# Advisory Quality Calibration — v1.5.1

**Status:** implemented
**Versions:** v1.5 (initial) → v1.5.1 (tightening)

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

---

## 8. v1.5.1 — SOFT_ACTION_ADVICE and Tightening

### 8.1 SOFT_ACTION_ADVICE Intent

New intent distinguishes "advisory guidance" from "formal execution":

- `SOFT_ACTION_ADVICE` triggers on: 操作建议, 怎么操作, 怎么处理, 该怎么办, 要不要动, 如何应对
- `FORMAL_TRADE_DECISION` triggers ONLY on explicit trade language: 买入, 卖出, 减仓, 加仓, 下单, 正式决策
- `"操作建议"` was REMOVED from FORMAL_TRADE_DECISION keywords
- `is_soft_advice_only()` helper added
- SOFT_ACTION_ADVICE alone does NOT require decision_support

### 8.2 Strict expected_behavior for ALL v1.5+ Fixtures

All fixtures now include:
- `expected_advisory_intents` — expected intent classification list
- `expected_chinese_summary_contains` — key Chinese phrases expected in summary
- 11 required expected_behavior keys validated for ALL_SCENARIOS_V15

### 8.3 Risk Profile A/B Calibration

Two explicit fixtures replace the single conservative_vs_aggressive:
- `same_portfolio_conservative_profile.json` — risk_level=conservative, max_trade_pct=0.05, max_buy=5000
- `same_portfolio_aggressive_profile.json` — risk_level=aggressive, max_trade_pct=0.15, max_buy=30000

Tests assert:
- Conservative execution_amount <= aggressive execution_amount
- Neither fabricates evidence anchors
- Neither contains broker/order fields

### 8.4 zh-CN Section Localization

All 8 section titles are localized to Chinese when language=zh-CN:
- direct_answer → 直接回答
- evidence_status → 证据状态
- portfolio_diagnosis → 组合诊断
- decision_explanation → 决策说明
- action_boundary → 操作边界
- recommended_next_steps → 建议下一步
- limitations → 限制与警告

Key sections include Chinese-text bullets:
- direct_answer: Chinese blocked/downgraded/formal status messages
- action_boundary: "不执行券商下单" safety text
- recommended_next_steps: Chinese missing-data and blocker guidance

### 8.5 final_report.py Modularization

Split into sub-modules without changing output contracts:
- `report_status.py` — normalize_language, compute_report_status, compute_decision_status, data_completeness_grade
- `report_safety.py` — FORBIDDEN_EXECUTION_FIELDS, find_forbidden_execution_fields, build_safety_boundary
- `report_zh.py` — ZH_CN_SECTION_TITLES, build_zh_blocked_reason, build_zh_downgraded_reason, build_chinese_summary, localize_section_titles
- `final_report.py` — imports from sub-modules, keeps section builders and compose_advisory_workflow_report

### 8.6 Non-Goals (Unchanged)

- No install/plugin/deployment changes.
- No network/provider SDK/broker execution.
- No LLM calls inside runtime.
- No new provider SDKs.
- No broker/order execution.
- fund_analysis still never emits formal Decision/ExecutionLedger.
- decision_support remains the only formal decision producer.
