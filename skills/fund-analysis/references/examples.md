# Fund Analysis Examples

## Analysis-Only Portfolio Report

User:

```text
分析下我的基金给出报告
```

Host flow:

1. Interpret objective as `portfolio_review`.
2. Collect portfolio, transactions, profiles, NAV history, holdings, DCA plans,
   risk profile, constraints, and optional market scenario.
3. Call `FundAnalysisSkill` with `skill_name="fund_analysis"`.
4. Write a report from artifacts and HardEvidence.
5. Do not call `decision_support` unless the user asks for formal trade advice.

## Formal Trade Advice

If the user asks:

```text
那我现在该买还是卖？
```

Host flow:

1. Compile `fund_analysis` evidence with `compile_evidence_graph`.
2. Extract `suggested_rebalance_plan`.
3. Call `DecisionSupportSkill` with `skill_name="decision_support"`.
4. Use the returned `Decision` and `ExecutionLedger` in the final answer.

## Chinese Report Snippet

```text
组合结论：当前组合最大问题不是单只基金短期亏损，而是权益和区域暴露偏集中。现金比例为 10%，在考虑新增买入前应先保留流动性缓冲。由于缺少部分持仓明细，行业集中度判断为 PARTIAL。
```
