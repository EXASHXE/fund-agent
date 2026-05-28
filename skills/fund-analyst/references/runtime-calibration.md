# 评分与裁量校准用例

本文件用于校准 Agent 的解释尺度。当前评分由纯工具层生成，Agent 不重新计算基准分；Agent 只做解释、风险复核和有限 `agent_overlay`。

## 校准原则

- 先读 `factor_matrix`，再解释 `composite_score`，最后看 `score_confidence`。
- 置信度低比总分更优先：`score_confidence < 0.7` 时，任何买入建议都必须降级为观察、维持或等待确认。
- 趋势判断服从 `trend_matrix`：短期上行不等于长期买入，中期下行必须限制加仓规模。
- 操作建议服从 `operation_advice`：目标仓位、调整金额和触发条件不由 Agent 手算。
- 组合建议服从 `portfolio_risk_matrix`：同簇拥挤和高相关重复要优先约束推荐。

---

## 校准用例 1：沪深 300 指数增强基金（中性偏优）

### 模拟结构化输出

| 字段 | 数值 |
|------|------|
| 数据完整度 | A |
| 综合分 | 70 |
| score_confidence | 0.92 |
| 宏观/中观/微观 | 15 / 19 / 36 |
| Sortino | 0.9 |
| Sharpe 1Y | 0.72 |
| Max Drawdown 3Y | 28.5% |
| Jensen Alpha | 0.018 |
| IR | 0.25 |
| HHI | 1800 |
| short_term trend | flat，confidence 0.58 |
| mid_term trend | flat，confidence 0.55 |
| operation_advice | hold，维持定投 |

### 期望解释

- 结论应为持有、维持定投或小幅优化，不应写成强买入。
- 重点解释指数增强的稳定 Alpha、回撤接近同类、置信度高。
- 如果 Agent overlay，幅度通常在 `[-3, +3]`，因为结构化因子没有重大矛盾。

### 禁止输出

- “趋势明确上行，建议大幅加仓。”
- “低风险稳健收益。”指数增强仍有权益波动。

---

## 校准用例 2：明星经理主动权益基金（高分但需看拥挤）

### 模拟结构化输出

| 字段 | 数值 |
|------|------|
| 数据完整度 | A |
| 综合分 | 84 |
| score_confidence | 0.94 |
| 宏观/中观/微观 | 17 / 24 / 43 |
| Sortino | 1.45 |
| Sharpe 1Y | 1.35 |
| Max Drawdown 3Y | 22.1% |
| Jensen Alpha | 0.061 |
| HHI | 2600 |
| short_term trend | up，confidence 0.70 |
| mid_term trend | flat，confidence 0.61 |
| portfolio cluster | growth_manufacturing 58% |
| operation_advice | hold 或小额分批，触发条件为回调后加仓 |

### 期望解释

- 可以认可基金质量高，但必须指出成长制造暴露已拥挤。
- 如果当前组合已经超配成长制造，不得把高分直接翻译为重仓加仓。
- 推荐语言应偏“回调分批”“维持核心仓”“不追高”。

### 禁止输出

- “评分高，立即加仓到最大仓位。”
- 忽略组合风险矩阵，仅从单基金质量下结论。

---

## 校准用例 3：高波动行业 ETF（低分锚）

### 模拟结构化输出

| 字段 | 数值 |
|------|------|
| 数据完整度 | A |
| 综合分 | 34 |
| score_confidence | 0.90 |
| 宏观/中观/微观 | 8 / 10 / 16 |
| Sortino | -0.2 |
| Sharpe 1Y | 0.18 |
| Max Drawdown 3Y | 48.0% |
| Beta | 1.12 |
| HHI | 4300 |
| short_term trend | down，confidence 0.68 |
| mid_term trend | down，confidence 0.64 |
| operation_advice | reduce 或 pause_dca |

### 期望解释

- 结论应为暂停新增、减仓或替换观察。
- 可以承认行业反弹弹性，但必须把它定义为高风险交易，不是长期核心仓。
- Agent overlay 不应把最终结论拉回买入，除非有强证据且必须写清触发条件。

### 禁止输出

- “跌得多所以估值便宜，建议抄底。”
- 用新闻热度覆盖下行趋势和低质量微观因子。

---

## 校准用例 4：数据完整度 C 的新基金（低置信度）

### 模拟结构化输出

| 字段 | 数值 |
|------|------|
| 数据完整度 | C |
| 综合分 | 66 |
| score_confidence | 0.60 |
| 中观 | N/A |
| factor_matrix | 多个因子 `missing_policy=neutral_when_missing` |
| short_term trend | up，confidence 0.42 |
| operation_advice | watch 或 hold |

### 期望解释

- 即使分数看起来不低，也只能给观察、维持或等待数据确认。
- 必须明确说明 C 级完整度可能放大宏观/微观折算信号。
- 不允许因为短期趋势上行而主动加仓。

### 禁止输出

- “评分 66，建议恢复定投。”
- “数据不足但可先买入试错。”除非结构化建议明确给出小额试仓。

---

## 组合层校准

| 检查项 | 期望结果 |
|--------|----------|
| 分数分布 | 3 只以上基金应有区分度，不应全部中性 |
| 置信度 | C/D 或缺失项多的基金必须在结论中降级 |
| 趋势一致性 | 文本方向必须匹配 `trend_matrix` |
| 操作一致性 | 文本动作必须匹配 `operation_advice` |
| 组合约束 | 高相关或同簇拥挤优先限制加仓 |
| Agent overlay | 偏离结构化建议时必须说明证据、幅度、风险和复核条件 |

如出现“评分 <45 仍建议加仓”“置信度 <0.7 仍建议买入”“成长制造已超 50% 仍推荐同簇新增”等情况，必须重新校准。
