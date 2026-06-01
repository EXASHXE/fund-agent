# 最终报告验收清单

本清单用于验收 `agent_decisions.v2` 和渲染的最终 `report.md`。

## 合同与口径

- [ ] `agent_decisions.schema_version` 为 `agent_decisions.v2`，且 `evidence_report_date` 等于证据稿 `report_date`。
- [ ] `fund_scores` 覆盖 evidence 中所有已评分基金；`news` 覆盖所有新闻证据对象；`recommendations` 明确存在，即使为空。
- [ ] 口径日后的新闻只出现在"不纳入当日归因"的观察区，未用于当天动作理由。
- [ ] 国内基金未被错误标成 QDII；QDII 仅提示披露可能滞后，不宣称净值必然为估算值。

## 分数与决策

- [ ] 每只基金宏观/中观/微观调整值均在 `[-10, +10]`。
- [ ] 每个最终分等于量化基准分加 Agent 调整，综合分等于三个分项之和。
- [ ] `final_action`、目标配置、执行金额、理由和触发条件均由 Agent 明确给出，不由量化候选自动回填。
- [ ] 所有数值目标配置合计不超过 100%，保留现金时已说明用途。
- [ ] 数据完整度低、低置信度、新闻覆盖窄或 pending 明显时，结论已保守降级并解释原因。
- [ ] `market_regime`（或 `regime`）已由评分引擎检测并写入 decisions，值在 `normal` / `high_volatility` / `trending` / `crisis` 中。
- [ ] 评分权重与 regime 匹配：对照 `scoring-agent.md` 中的 regime 权重表，确认各维度权重使用正确。
- [ ] `strategy_advice` 已为每只评分基金生成，包含 `action`、`confidence`、`risk_level`、`reasons`、`stop_loss_pct`、`valid_transitions`。
- [ ] `strategy_advice.action` 与 `fund_scores.{code}.final_action` 一致；不一致时必须有理有据解释。
- [ ] 5 维度评分（quant / fundamental / event / position / timing）各自 0-100 分，综合分在 0-100 范围内，等级映射正确（green ≥80、yellow 60-79、orange 40-59、red ≤39）。

## 新闻与组合风险

- [ ] 每个新闻结论引用了有效样本数量、覆盖限制与置信度；低相关样本未支撑买入或加仓。
- [ ] 组合判断考虑了相关性、暴露集中、压力结果、pending 和净值结算状态。
- [ ] 最终推荐对象来自本次 `recommendation_evidence.candidates` 且写明组合角色和风险约束；空数组不出现规则候选结论。
- [ ] `event_extraction` 如有生成，其 `affected_holdings` 与重仓股列表覆盖一致。
- [ ] `kg_analysis.cross_fund_links` 如有生成，`correlation_risk` 判断与 `portfolio_evidence` 中的相关性矩阵一致。

## 报告完整性

- [ ] 报告状态为 `Agent 最终研判`，包含一至七章和风险提示。
- [ ] "申购与净值结算状态"覆盖全部持仓，且在定投执行表之后。
- [ ] 单基金诊断折叠块均闭合，止盈止损线有单位并能与风险证据对应。
- [ ] 报告中不存在 `AGENT_FILL`、`<!-- AGENT:`、`尚未提供 agent`、`待 Agent 最终评定`、旧规则动作章节。

验证检查：报告输出中不得包含 `AGENT_FILL`、`<!-- AGENT:`、`尚未提供 agent`、`待 Agent 最终评定` 等占位符，否则不交付最终稿。
