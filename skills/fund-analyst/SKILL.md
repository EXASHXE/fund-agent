---
name: fund-analyst
description: 基于基金持仓、净值、新闻覆盖证据和组合风险进行战略投研与资产配置决策。用于运行 fund-agent 分析、读取 report.evidence.json、生成 agent_decisions.v2 并渲染无占位符的最终报告。
---

# 基金战略投研与资产配置

本 Skill 将 Python 引擎视为**证据计算层**，将 Agent 视为**最终决策层**。最终动作、目标配置和执行金额只能写入 `agent_decisions.json`，再由 CLI 渲染成最终报告。

## 不可违反的边界

1. `report.evidence.json` 是决策的结构化事实输入；`report.md` 在首次运行时只是可读的证据稿。
2. 不把 `quant_baseline`、`trend_evidence`、候选筛选结果直接称为投资结论。
3. 不从新闻标题推断未覆盖的持仓风险；必须引用 `news_evidence.evaluation` 的覆盖限制。
4. 口径日后的新闻只能作为观察，不能纳入口径日归因或动作依据。
5. `agent_adjustments` 的宏观/中观/微观分项各限于 `[-10, +10]`，最终分必须与基准分及修正值可对账。
6. C/D 完整度、关键因子缺失或低置信度证据，动作应为 `hold`、`observe`、`pause_dca` 或 `insufficient_evidence`，不得强行买入。
7. 仅结构化类型为 QDII 或名称明确包含 `QDII` 时使用海外净值滞后提示；不能因“石油”“全球”等名称推定为 QDII。
8. 不在最终稿中留下 `AGENT_FILL`、`<!-- AGENT:`、规则动作章节或“待 Agent 最终评定”文本。

## 标准工作流

### 1. 生成证据稿

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --no-snapshot-after
```

需要候选或压力情景时显式加入 `--recommend`、`--stress`。默认关闭两项，避免把未请求的外部筛选混入结论。

若 CLI 生成 `report.news_keywords_request.json` 后停止：

1. 读取请求中的基金和重仓股。
2. 按“原子关键词规则”生成 `data/cache/news_keyword_profiles.json`。
3. 重跑上面的分析命令；也可由用户授权使用 `--fallback-keywords`。

### 2. 审核证据

读取本次输出的 `report.evidence.json`，逐项核验：

- `report_date`：本次决策唯一允许使用的口径日。
- `funds.*.holding_metrics`：市值、收益、pending、净值日期和结算证据。
- `funds.*.quant_baseline` 与 `factor_matrix`：量化基准和缺失策略。
- `funds.*.trend_evidence`：方向性证据，不是自动动作。
- `funds.*.risk_constraints`：当前权重、QDII/pending/定投约束。
- `funds.*.news_evidence`：截至口径日样本、覆盖警告和口径日后观察。
- `portfolio_evidence`：相关性、压力测试和组合暴露约束。
- `workflow_evidence`：定投计划与全部持仓的申购/净值结算状态。
- `recommendation_evidence`：规则筛选候选，仅作为 Agent 是否推荐的输入。

事实不完整时，在决策理由中明确“证据不足”及所需复核项，不补造数据。

### 3. 形成 `agent_decisions.json`

必须使用以下合同。每只证据稿中已评分的基金都要有一条 `fund_scores`；每只有新闻证据对象的基金都要有一条 `news`；没有最终推荐时仍写空数组。

```json
{
  "schema_version": "agent_decisions.v2",
  "evidence_report_date": "2026-05-22",
  "portfolio": {
    "stance": "neutral",
    "tldr": "组合级最终判断",
    "risk_summary": ["组合风险结论"],
    "execution_notes": ["执行节奏与复核约束"]
  },
  "news": {
    "000001": {
      "summary": "与重仓链条相关的新闻结论或样本不足说明",
      "impact": "positive|neutral|negative|mixed|insufficient_evidence",
      "relevance": "high|medium|low|insufficient_evidence",
      "confidence": 0.0,
      "watch": ["需验证的事件"]
    }
  },
  "fund_scores": {
    "000001": {
      "agent_adjustments": {"macro": 0, "meso": 0, "micro": 0},
      "final_scores": {"macro": 15, "meso": 22, "micro": 39, "total": 76},
      "final_action": "hold",
      "target_weight_pct": null,
      "adjust_amount": null,
      "rationale": ["基于 evidence 的结论依据"],
      "triggers": ["可检查、可执行的复核触发条件"],
      "trend_view": "对趋势证据的审慎解释"
    }
  },
  "recommendations": []
}
```

对账规则：

- `final_scores.macro = quant_baseline.macro_score + agent_adjustments.macro`，中观、微观同理。
- `final_scores.total = final_scores.macro + final_scores.meso + final_scores.micro`。
- `target_weight_pct` 与 `adjust_amount` 由 Agent 在组合约束下决策；不能抄写旧规则动作或将候选自动升级为推荐。
- 已给出数值的 `target_weight_pct` 合计不得超过 100%；现金留存可使合计低于 100%。
- 最终推荐只能选自本次 `recommendation_evidence.candidates`；未启用候选筛选时输出空数组。
- `rationale` 至少说明证据、约束和结论之间的链路；`triggers` 必须是后续可复核的条件。

### 4. 渲染最终报告

在相同口径日窗口内运行：

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md \
  --agent-decisions agent_decisions.json --no-snapshot-after
```

需要与证据稿一致的 `--recommend` / `--stress` 配置。CLI 会拒绝日期不匹配、缺基金决策、分数无法对账或最终稿合同不完整的输入。口径日改变后，废弃旧 decisions，重新从证据稿决策。

### 5. 验收

读取 [checklist.md](checklist.md) 并逐项检查。最低验收命令：

```bash
grep -n "AGENT_FILL\|<!-- AGENT:\|尚未提供 agent\|待 Agent 最终评定" report.md
```

结果必须为空；最终稿须显示 `Agent 最终研判`、七个固定章节、新闻覆盖限制、全基金结算状态和风险提示。

## 新闻关键词规则

关键词缓存仅用于召回证据，不得决定动作：

- 每个关键词是无空格原子实体，例如 `"英伟达"`、`"台积电"`、`"HBM"`。
- 优先重仓公司及可验证产业链实体；禁止 `"市场"`、`"走势"`、`"估值"` 等泛词。
- 新闻覆盖偏窄、无穿透持仓或样本质量低时，在 `news` 决策中降置信度并写清限制。

## 决策尺度

- 高基准分不自动等于加仓；先检查集中度、相关性、pending、结算时滞和数据完整度。
- 短期正向新闻不能覆盖中期风险或低覆盖警告。
- 推荐池是证据候选。只有 `agent_decisions.recommendations` 中的对象才会成为最终推荐。
- 净值披露早于口径日时，说明口径限制，不能把滞后变化解释为当日市场结果。

## 按需参考

- 输出前必须读 [checklist.md](checklist.md)。
- 需要决策尺度示例时读 [examples.md](examples.md) 与 [calibration.md](calibration.md)。
- 需要生成新闻关键词或核对 AKShare 字段时读 [akshare-ref.md](akshare-ref.md)。
