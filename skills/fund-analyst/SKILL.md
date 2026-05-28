---
name: fund-analyst
description: 基于基金持仓、净值、新闻覆盖证据和组合风险进行战略投研与资产配置决策。用于运行 fund-agent 分析、读取 report.evidence.json、生成 agent_decisions.v2 并渲染无占位符的最终报告。
---

# 基金战略投研与资产配置

本 Skill 将 Python 引擎视为**证据计算层**，将 Agent 视为**最终决策层**。最终动作、目标配置和执行金额只能写入 `agent_decisions.json`，再由 CLI 渲染成最终报告。

## 工作流

### 标准流水线（3因子评分）

1. 运行证据稿：

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --no-snapshot-after
```

需要候选或压力情景时显式加入 `--recommend`、`--stress`。默认关闭两项，避免把未请求的外部筛选混入结论。

### Agent 增强流水线（5维度评分）

当提供 `--use-agents` 标志时，CLI 将激活 LangGraph 多 Agent 流水线，由以下模块协同决策：

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --use-agents --no-snapshot-after
```

该模式下的关键变化：

- **评分引擎升级**：原 3 因子（宏观/中观/微观，权重 20%/30%/50%）替换为 5 维度评分系统（量化/基本面/事件/持仓/择时，各 0-100 分），结合市场 regime 动态调整权重
- **事件抽取**：NLP 模块提取结构化事件（公告、分红、经理变更等），纳入证据层
- **知识图谱分析**：KG 模块补充基金间关联、行业暴露和影响链
- **策略引擎**：产出 `strategy_advice`，包含止损、止盈和仓位调整建议
- 输出 JSON 中新增 `event_extraction`、`kg_analysis` 和 `strategy_advice` 字段

切换回标准模式只需去掉 `--use-agents`。

2. 审核 `report.evidence.json`：

- `report_date` 是唯一允许使用的口径日。
- `funds.*.quant_baseline`、`factor_matrix`、`trend_evidence` 是证据，不是自动动作。
- `funds.*.news_evidence` 必须结合覆盖限制、口径日后观察和 `relevance_task` 判断。
- `portfolio_evidence`、`workflow_evidence`、`recommendation_evidence` 只作为 Agent 决策输入。

3. 生成 `agent_decisions.json`，合同见 `references/decision-contract.md`。

4. 渲染最终报告：

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md \
  --agent-decisions agent_decisions.json --no-snapshot-after
```

口径日改变后，废弃旧 decisions，重新从证据稿决策。

## 不可违反的边界

1. `report.evidence.json` 是结构化事实输入；首次 `report.md` 只是可读证据稿。
2. 不把 `quant_baseline`、`trend_evidence`、候选筛选结果直接称为投资结论。
3. 不从新闻标题推断未覆盖的持仓风险；必须引用 `news_evidence.evaluation` 的覆盖限制。
4. 口径日后的新闻只能作为观察，不能纳入口径日归因或动作依据。
5. `agent_adjustments` 的宏观/中观/微观分项各限于 `[-10, +10]`，最终分必须与基准分及修正值可对账。（`--use-agents` 模式下使用 5 维度评分替换 3 因子）
6. C/D 完整度、关键因子缺失或低置信度证据，动作应保守，不能强行买入。
7. 仅结构化类型为 QDII 或名称明确包含 `QDII` 时使用海外净值滞后提示。
8. 不在最终稿中留下 `AGENT_FILL`、`<!-- AGENT:`、规则动作章节或“待 Agent 最终评定”文本。
9. `--use-agents` 模式下，`strategy_advice` 和 `regime` 字段由策略引擎产出，Agent 可调整但不可删除。regime 权重变更必须与市场环境对账。

## Prompt 模块

- `prompts/router.md`：决定本轮需要哪些子 Agent。
- `prompts/news-agent.md`：按重仓实体和新闻覆盖限制形成新闻意见。
- `prompts/scoring-agent.md`：解释量化基准，并生成可对账的调整分；`--use-agents` 模式下升级为 5 维度评分（quant / fundamental / event / position / timing），含 regime 感知动态权重。

## 按需参考

- 输出前必须读 `references/checklist.md`。
- 合同字段见 `references/evidence-contract.md` 和 `references/decision-contract.md`。
- 需要决策尺度示例时读 `references/examples.md` 与 `references/calibration.md`。
- 需要生成新闻关键词或核对 AKShare 字段时读 `references/akshare-ref.md`。
