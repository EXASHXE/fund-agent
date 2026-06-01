# WAIT/HOLD Policy

WAIT and HOLD are formal decisions, not filler.

## Required Explanation

Every WAIT/HOLD decision should explain:

- why not buy;
- why not sell;
- what evidence is missing;
- what trigger would change the recommendation;
- what invalidates the current stance.

## Example

```json
{
  "action": "HOLD",
  "execution_amount": 0,
  "trigger_conditions": [
    "Downgraded to HOLD: no valid trade-specific evidence anchors in evidence graph"
  ],
  "invalidating_conditions": [
    "New evidence contradicts the concentration risk assessment",
    "Cash reserve falls below required liquidity buffer"
  ]
}
```

## Host Language

```text
当前不是买入结论，因为缺少支持加仓的交易级证据；也不是卖出结论，因为现有证据只显示集中度风险，未证明该基金长期逻辑失效。若补充到有效 evidence_refs 且现金预算充足，可重新评估。
```
