# 决策裁量校准

此文件用于约束 `agent_decisions.v2` 的决策尺度。代码生成证据，Agent 对证据负责并形成最终动作。

## 通用规则

- 先读 `factor_matrix` 和数据完整度，再读 `quant_baseline`，最后结合 `trend_evidence` 与组合约束决策。
- `score_confidence < 0.7`、C/D 完整度或显著缺失字段优先输出 `observe` / `hold` / `insufficient_evidence`。
- `trend_evidence` 是方向证据，不是交易命令；不得与证据方向相反描述而不给理由。
- `risk_constraints`、相关性、暴露簇、pending 与结算时滞可以约束或否决新增配置。
- 最终动作、目标配置与金额必须写入 decisions，且理由和触发条件足以复核。

## 校准用例

| 证据情形 | 合理决策尺度 | 禁止行为 |
|----------|--------------|----------|
| A 级完整度、基准 70、趋势中性、风险正常 | `hold` 或维持既有计划；调整通常接近 0 | 仅因分数不低直接大幅加仓 |
| A 级高分、趋势偏强，但同簇或海外暴露集中 | 保留质量判断，动作可为 `hold`/`reduce`；写清组合预算约束 | 忽略集中度给出无条件新增 |
| 高波动行业、基准低、趋势走弱、回撤明显 | `pause_dca`、`reduce` 或 `observe` | 用反弹想象覆盖负向证据 |
| C 级或置信度低，短期趋势略正 | `observe` 或 `insufficient_evidence`；目标与金额可为 null | 以短期信号支持主动买入 |
| 新闻情绪偏正但覆盖权重低 | 新闻影响为低置信或证据不足，不提高动作强度 | 把少量标题解释为全基金催化 |

## 分数对账

假设某基金证据基准为宏观 15、中观 22、微观 35，Agent 因集中度把中观下调 2 分：

```json
{
  "agent_adjustments": {"macro": 0, "meso": -2, "micro": 0},
  "final_scores": {"macro": 15, "meso": 20, "micro": 35, "total": 70}
}
```

以下决策无效：

- 任一调整超过 `[-10, +10]`。
- 最终分与基准加调整不一致。
- 综合分不等于最终三个分项之和。
- 只有动作或金额，没有理由及可复核触发条件。

## 新闻与推荐校准

- `news.evaluation.coverage_warning` 非空时，新闻正文必须复述限制并降低信心。
- `post_cutoff_news` 不能支撑口径日动作。
- 候选筛选不具有最终推荐身份；`recommendations: []` 是有效的审慎结论。
