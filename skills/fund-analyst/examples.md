# 参考输出示例

以下示例用于校准输出风格。示例中的分数、趋势、目标仓位、调整金额均视为 CLI 已生成的结构化结果，Agent 只解释，不重算覆盖。

---

## 示例 1：单只国内混合型基金（完整度 A）

### CLI 结构化输入摘要

```text
基金：测试稳健成长混合（110011）
数据完整度：A
综合评分：72，score_confidence：0.91
feature_matrix：Sortino 0.88，Sharpe 1Y 1.05，Jensen Alpha 0.032，IR 0.41，Beta 0.92，Max Drawdown 18.5%，HHI 2100
trend_matrix：short_term flat / 0.57 / confidence 0.62；mid_term up / 0.66 / confidence 0.58
operation_advice：hold，target_weight 18%，adjust_amount 0，triggers=["评分稳定且中期趋势改善", "回撤扩大至25%暂停新增"]
```

### 期望输出片段

```markdown
#### 诊断分析

这只基金的规则综合分为 72 分，`score_confidence=0.91`，说明当前结论主要由完整净值、绩效和持仓数据支撑，不属于低置信度推断。因子拆解中，Sortino 0.88 与 Sharpe 1.05 表明风险调整收益处于中上水平；Jensen Alpha 为正，说明基金经理仍有一定主动超额，但 HHI 2100 显示持仓已进入中度集中区间。

趋势矩阵给出的短期方向为震荡，中期方向为上行。操作上不应追高加仓，而是维持现有目标仓位 18%，等待中期趋势继续确认。若后续回撤扩大至 25% 或评分跌破 60，应暂停新增；若中期趋势分维持在 0.65 以上且新闻催化不转负，可以恢复小额定投。
```

---

## 示例 2：QDII 成长基金（高分但组合拥挤）

### CLI 结构化输入摘要

```text
基金：海外科技精选 QDII（017436）
数据完整度：A
综合评分：81，score_confidence：0.93
trend_matrix：short_term up / 0.71 / confidence 0.69；mid_term flat / 0.59 / confidence 0.55
operation_advice：hold，target_weight 22%，adjust_amount -1500，triggers=["QDII pending 高于计划阈值", "成长制造与海外敞口偏高"]
portfolio_risk_matrix：overseas 42%，growth_manufacturing 56%，warnings=["growth_manufacturing 暴露 56%，超过组合集中度阈值"]
```

### 期望输出片段

```markdown
#### 风险与再平衡

海外科技基金本身评分较高，短期趋势也偏上行，但组合层面的约束更强：海外敞口已达到 42%，成长制造暴露达到 56%，属于同一增长因子过度集中。结构化建议给出 `hold` 且调整金额为 -¥1,500，核心原因不是否定基金质量，而是降低组合对单一科技成长链条和 QDII 净值延迟的依赖。

因此，本基金适合保留核心仓位，但不适合继续加速定投。新增资金应优先补防守现金流或红利低波资产；若海外科技回撤后短期趋势仍保持上行，再按结构化触发条件重新评估。
```

---

## 示例 3：新闻低相关，不纳入买入理由

### CLI 结构化输入摘要

```text
基金：医药创新混合（003095）
综合评分：58，score_confidence：0.82
news_evaluation：relevance_score 0.18，overall_score 0.05，negative_density 0.34
trend_matrix：short_term down / 0.39 / confidence 0.60；mid_term flat / 0.48 / confidence 0.52
operation_advice：pause_dca，target_weight 10%，adjust_amount -800
```

### 期望输出片段

```markdown
#### 新闻解读

本组新闻的相关性分仅 0.18，不能作为该基金的买入依据。虽然部分标题涉及医药政策边际改善，但与基金重仓链条的匹配度不足，且负向新闻密度仍偏高。趋势矩阵已经把短期方向判为下行，因此当前更合理的动作是暂停新增并等待重仓股业绩或政策催化出现可验证改善。
```

---

## 示例 4：数据完整度 C 的新基金

### CLI 结构化输入摘要

```text
基金：新材料精选混合（019888）
数据完整度：C
综合评分：64，score_confidence：0.60
factor_matrix：中观缺失；多个微观因子 missing_policy=neutral_when_missing
trend_matrix：short_term up / 0.54 / confidence 0.41；mid_term flat / 0.47 / confidence 0.38
operation_advice：watch，target_weight 3%，adjust_amount 0，triggers=["数据完整度不足", "趋势置信度低"]
```

### 期望输出片段

```markdown
#### 诊断分析

这只基金的表观分为 64，但 `score_confidence=0.60`，必须按低置信度处理。中观持仓和行业因子缺失，多个微观指标使用中性缺失策略，说明分数只适合做观察参考，不能转化为主动加仓结论。

短期趋势虽然略高于中性，但趋势置信度只有 0.41。结构化建议为 `watch`，目标权重 3%，当前不调整。后续只有在披露完整持仓、Sortino/Sharpe 等核心因子可验证、趋势置信度提升后，才允许重新讨论定投或加仓。
```

---

## 示例 5：推荐候选受组合风险预算约束

### CLI 结构化输入摘要

```text
候选 A：半导体芯片基金，score 0.63，exposure_cluster growth_manufacturing，risk_budget_impact="成长制造已拥挤，新增会提高回撤风险"
候选 B：中短债债券基金，score 0.71，exposure_cluster defensive_income，entry_plan="分批买入"，risk_budget_impact="补足防守资产，降低组合波动"
portfolio_risk_matrix：growth_manufacturing 75%，defensive_income 0%
```

### 期望输出片段

```markdown
#### 推荐基金解释

本次推荐排序优先选择中短债债券基金，并不是因为其短期弹性更高，而是因为组合已经有 75% 暴露在成长制造簇，防守现金流暴露为 0%。结构化排序把防守缺口转化为风险预算加分，因此该候选的进入计划是“分批买入”。半导体候选只适合作为替代观察，不能在现有组合上继续叠加同簇风险。
```
