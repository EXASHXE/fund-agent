# Advisory Quality Gate and Workflow Trace — v1.6.2

## Why the Quality Gate Exists

The advisory workflow produces multiple outputs (fund_analysis, evidence_graph, decision_support, final_report) that must satisfy strict safety and quality boundaries. The quality gate provides a deterministic, automated check that these boundaries are respected.

Without the gate, a code change could accidentally:
- Allow fund_analysis to emit a formal Decision (violating the skill boundary)
- Allow broker/order execution fields to leak into the report
- Allow an active BUY/SELL decision without evidence anchors
- Omit required Chinese-language disclosures for zh-CN scenarios

## Check List

| # | Check ID | Purpose | FAIL condition |
|---|----------|---------|----------------|
| 1 | fund_analysis_no_formal_decision | fund_analysis must not emit Decision/ExecutionLedger/broker fields | Any forbidden key or field found |
| 2 | formal_source_boundary | Formal decisions must come from decision_support only | decision_status is FORMAL_DECISION but source is not decision_support |
| 3 | report_only_no_decision_support | Report-only scenarios must not have decision_support output | decision_support_called=false but ds_output present |
| 4 | decision_support_required_artifacts | decision_support must produce required artifacts | Missing execution_ledger, ledger_summary, evidence_anchor_diagnostics, or risk_constraint_conflicts |
| 5 | active_trade_anchor_gate | Active BUY/SELL/INCREASE/REDUCE must have evidence anchors | Active decision allowed without anchors |
| 6 | missing_data_disclosed | Missing data indicators must be disclosed in final report | Missing data found but not disclosed (WARN) |
| 7 | no_broker_execution | No broker/order execution fields anywhere | Forbidden fields found in any output |
| 8 | action_boundary_present | final_report must include action_boundary with disclaimers | Missing section or missing disclaimers |
| 9 | zh_direct_answer_present | zh-CN reports must have direct_answer and chinese_summary with Chinese text | Missing section or no Chinese text |
| 10 | suggested_rebalance_analysis_only | suggested_rebalance_plan must be analysis-only | Contains broker fields or not disclosed as analysis-only |
| 11 | provider_data_provenance_present | Provider-derived data must have source/provenance/as_of | Missing provenance (WARN or FAIL) |

## Trace Event Model

The workflow trace records deterministic events in sequence order:

```
[1] input_loaded: Loaded personal regression fixture
[2] intent_classified: Intents: REPORT_ONLY, CASH_DEPLOYMENT
[3] fund_analysis_started: Starting fund_analysis
[4] fund_analysis_completed: fund_analysis completed
[5] evidence_graph_started: Building evidence graph
[6] evidence_graph_built: Evidence graph built
[7] decision_support_started/decision_support_skipped
[8] decision_support_completed (if called)
[9] final_report_started: Composing final report
[10] final_report_composed: Final report composed
[11] quality_gate_started: Evaluating quality gate
[12] quality_gate_evaluated: Quality gate evaluated
[13] workflow_completed: Workflow completed
```

## How Runner Uses Trace

The personal regression runner (`tests/helpers/personal_regression_runner.py`) builds a `WorkflowTrace` during each scenario run. The trace is included in `PersonalRegressionResult.workflow_trace` and propagated to the CLI script.

## How to Interpret FAIL/WARN

- **PASS**: Check satisfied, no action needed.
- **WARN**: Check partially satisfied or potentially problematic. Review recommended but not blocking.
- **FAIL**: Check violated. Must be fixed before the workflow output is acceptable.

The overall gate `passed` field is `true` only when all checks are PASS or WARN (no FAIL).

## No Chain-of-Thought Policy

The trace and gate never include chain-of-thought reasoning, internal deliberation, or LLM-generated explanations. All messages are deterministic and factual.

## No Secrets Policy

The trace automatically redacts any field whose key contains `api_key`, `token`, `cookie`, `password`, `secret`, or `authorization`. Values are replaced with `<redacted>`.
