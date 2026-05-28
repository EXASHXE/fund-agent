# agent_decisions.v2 合同

最终动作、目标配置、执行金额、新闻研判和推荐只能来自 `agent_decisions.json`。

## 最小结构

```json
{
  "schema_version": "agent_decisions.v2",
  "evidence_report_date": "2026-05-22",
  "portfolio": {
    "stance": "neutral",
    "tldr": "组合级最终判断",
    "risk_summary": ["组合风险结论"],
    "execution_notes": ["执行节奏与复核约束"],
    "daily_analysis": "当日组合级盈亏归因与整体研判总结"
  },
  "news": {
    "000001": {
      "summary": "与重仓链条相关的新闻结论或样本不足说明",
      "impact": "positive|neutral|negative|mixed|insufficient_evidence",
      "relevance": "high|medium|low|insufficient_evidence",
      "confidence": 0.0,
      "watch": ["需验证的事件"],
      "key_news": [
        {"title": "关键新闻标题", "reason": "影响路径"}
      ]
    }
  },
  "fund_scores": {
    "000001": {
      "agent_adjustments": {"macro": 1, "meso": -2, "micro": 0},
      "final_scores": {"macro": 16, "meso": 20, "micro": 39, "total": 75},
      "final_action": "hold",
      "target_weight_pct": null,
      "adjust_amount": null,
      "suggested_stop_profit_pct": 25.0,
      "suggested_stop_loss_pct": -15.0,
      "daily_attribution": "基金专属当日归因",
      "rationale": ["基于 evidence 的结论依据"],
      "triggers": ["可检查、可执行的复核触发条件"],
      "trend_view": "对趋势证据的审慎解释",
      "regime": "normal",
      "strategy_advice": null
    }
  },
  "recommendations": []
}
```

## 新增字段（Agent 增强模式，`--use-agents`）

### regime

每只基金可携带 `regime` 字段，表示当前市场环境分类：

| 值 | 含义 | 典型特征 |
|----|------|----------|
| `normal` | 正常市场 | 波动率适中，趋势不明，量化因子权重最高 |
| `high_volatility` | 高波动 | VIX 偏高，日内振幅大，强调事件和择时 |
| `trending` | 趋势行情 | 明确上/下趋势，跟随趋势，提高持仓权重 |
| `crisis` | 危机模式 | 极端行情，避险优先，事件和择时主导 |

`regime` 为可选字段。标准模式（未使用 `--use-agents`）下可为 `null` 或缺失。当存在时，应确保评分 Agent 使用的权重与 regime 匹配。

### strategy_advice

当策略引擎被激活（`--use-agents` 模式）时，每只基金可携带 `strategy_advice` 节：

```json
{
  "action": "hold",
  "confidence": 0.75,
  "risk_level": "medium",
  "reasons": [
    "评分66分，维持当前仓位",
    "无重大负面事件"
  ],
  "position_suggestion": "维持当前仓位",
  "stop_loss_pct": 15.0,
  "state": "hold",
  "valid_transitions": {"hold": ["add", "reduce", "wait"]}
}
```

`StrategyAdvice` 字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | string | 策略动作：hold（持有）、add（加仓）、reduce（减仓）、wait（观望） |
| `confidence` | float | 动作置信度 0.0-1.0 |
| `risk_level` | enum | 风险等级：low / medium / high / critical |
| `reasons` | string[] | 动作理由列表，每条一句话 |
| `position_suggestion` | string | 仓位调整建议的自然语言描述 |
| `stop_loss_pct` | float | 止损百分比（正数，如 15.0 表示跌 15% 止损） |
| `state` | string | 策略引擎当前状态机状态 |
| `valid_transitions` | object | 从当前状态允许的合法转移目标及说明 |

`strategy_advice` 为可选字段。标准模式下可为 `null` 或缺失。Agent 可调整 `strategy_advice` 中的值，但不建议删除整个节；若确需删除，应在 `rationale` 中说明理由。

## 评分字段互斥规则

同一份 decisions 中，两种评分模式不可混用：

- **标准模式**（无 `--use-agents`）：使用 `agent_adjustments.{macro,meso,micro}` 和 `final_scores.{macro,meso,micro,total}`
- **Agent 增强模式**（`--use-agents`）：使用 `event_extraction`、`kg_analysis`、`regime`、`strategy_advice` 等新字段；`agent_adjustments` 仍可存在但作用于 5 维度引擎

## 对账规则

- `final_scores.macro = quant_baseline.macro_score + agent_adjustments.macro`，中观、微观同理。
- `agent_adjustments` 各分项必须在 `[-10, +10]`。
- `final_scores.total = final_scores.macro + final_scores.meso + final_scores.micro`。
- 已给出数值的 `target_weight_pct` 合计不得超过 100%。
- 每只已评分基金都要有 `fund_scores`。
- 每只有新闻证据对象的基金都要有 `news`。
- 没有最终推荐时仍写空数组。

## 文本质量要求

- `rationale` 中的事实必须引用 evidence 中明确给出的新闻事件、持仓变化或量化指标。
- 当量化基准与新闻证据背离时，必须说明背离原因和处理方式。
- `triggers` 必须是具体可量化、可复核的事件或阈值。
- `daily_attribution` 必须为每只基金提供专属归因，不能复用套话。
