# 决策输出示例

示例演示如何把 evidence 转为 `agent_decisions.v2`。数值仅为格式样例；实际输出必须来自本次 `report.evidence.json`。

## 示例一：证据充分但保持持有

Evidence 摘要：

```json
{
  "quant_baseline": {"macro_score": 15, "meso_score": 22, "micro_score": 35, "total_score": 72, "score_confidence": 0.91},
  "trend_evidence": {"short_term": {"direction": "flat"}, "mid_term": {"direction": "up"}},
  "risk_constraints": {"current_weight": 0.18, "pending_amount": 0}
}
```

决策片段：

```json
{
  "agent_adjustments": {"macro": 0, "meso": 0, "micro": 0},
  "final_scores": {"macro": 15, "meso": 22, "micro": 35, "total": 72},
  "final_action": "hold",
  "target_weight_pct": 18.0,
  "adjust_amount": 0,
  "rationale": ["因子覆盖充分，中期趋势改善但短期未形成增配证据"],
  "triggers": ["若最大回撤扩大至风险阈值或中期趋势转弱，复核定投计划"]
}
```

要点：高置信度允许形成判断，但短期中性时不把分数自动翻译成加仓。

## 示例二：QDII 高分但组合集中

Evidence 摘要：

```json
{
  "identity": {"fund_type": "qdii"},
  "quant_baseline": {"macro_score": 17, "meso_score": 24, "micro_score": 40, "total_score": 81},
  "risk_constraints": {"current_weight": 0.25, "pending_amount": 3000, "is_qdii": true},
  "portfolio_evidence": {"risk_matrix": {"warnings": ["海外成长暴露集中"]}}
}
```

决策片段：

```json
{
  "agent_adjustments": {"macro": 0, "meso": -2, "micro": 0},
  "final_scores": {"macro": 17, "meso": 22, "micro": 40, "total": 79},
  "final_action": "reduce",
  "target_weight_pct": 22.0,
  "adjust_amount": -1500,
  "rationale": ["基金质量证据偏强，但海外成长集中且存在待确认资金与披露时滞"],
  "triggers": ["pending 全部确认后重新核验实际占比", "海外成长集中度降至预算内再评估新增"]
}
```

要点：Agent 可以在有依据时确定执行金额，但必须把组合约束写入理由和触发条件。

## 示例三：新闻覆盖不足

Evidence 摘要：

```json
{
  "news_count": 2,
  "evaluation": {
    "quality_score": 0.2,
    "holding_coverage_count": 1,
    "holding_coverage_pct": 0.12,
    "coverage_warning": "新闻覆盖偏窄，不能代表基金已披露重仓敞口"
  }
}
```

新闻决策片段：

```json
{
  "summary": "样本仅覆盖少量重仓实体，不能用于推断整只基金的收益来源",
  "impact": "insufficient_evidence",
  "relevance": "low",
  "confidence": 0.2,
  "watch": ["补充覆盖主要持仓的直接事件证据后再复核"]
}
```

要点：高情绪信号不覆盖低相关性和低持仓覆盖限制。

## 示例四：候选池不自动变成推荐

当 evidence 中存在候选，但组合已集中于相同风险簇且 Agent 不认可新增配置时：

```json
{
  "recommendations": []
}
```

最终报告应说明本次 Agent 未给出最终推荐，而不是显示候选基金为行动结论。
