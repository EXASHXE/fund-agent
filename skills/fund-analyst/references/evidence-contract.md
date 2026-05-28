# report_evidence.v2 合同

`report.evidence.json` 是 Agent 决策的唯一结构化事实输入。

## 顶层字段

- `schema_version`：固定为 `report_evidence.v2`。
- `report_date`：本次决策唯一允许使用的口径日。
- `report_status`：证据稿状态，通常为 `awaiting_agent_decisions`。
- `portfolio`：组合级市值、成本、盈亏和当日归因线索。
- `funds`：按基金代码索引的证据对象。
- `portfolio_evidence`：相关性、压力测试和组合风险矩阵。
- `workflow_evidence`：定投、申购、净值结算和组合新闻线索。
- `recommendation_evidence`：规则候选池，仅供 Agent 复核。
- `event_extraction`：（可选，`--use-agents` 模式）结构化事件抽取结果。
- `kg_analysis`：（可选，`--use-agents` 模式）知识图谱分析结果。

## 单基金字段

- `identity`：代码、名称、基金类型、数据完整度。
- `holding_metrics`：当前市值、成本、收益、pending、净值日期和结算证据。
- `quant_baseline`：宏观/中观/微观/总分和评分置信度。
- `factor_matrix`：可解释评分因子。
- `trend_evidence`：趋势证据，不是交易命令。
- `risk_constraints`：当前权重、pending、QDII、DCA 等约束。
- `news_evidence`：新闻数量、压缩摘要、覆盖评估、样本、口径日后观察和相关性任务。
- `event_extraction`：（可选，仅 `--use-agents` 模式）该基金的结构化事件列表。

## 事件抽取（event_extraction）

当 `--use-agents` 标志激活时，NLP 模块对每只基金产生 `event_extraction` 节。每条事件使用 `ExtractedEvent` 结构：

```json
{
  "fund_code": "000001",
  "extracted_events": [
    {
      "event_id": "evt_001",
      "event_type": "dividend|announcement|manager_change|regulatory|market_event",
      "title": "事件标题",
      "date": "2026-05-22",
      "impact_direction": "bullish|bearish|neutral",
      "impact_score": 0.75,
      "confidence": 0.85,
      "affected_holdings": ["600519"],
      "summary": "一句话事件摘要"
    }
  ],
  "summary_stats": {
    "total_events": 5,
    "bullish_count": 3,
    "bearish_count": 1,
    "neutral_count": 1,
    "high_impact_count": 2
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件唯一标识 |
| `event_type` | enum | 事件类型：dividend（分红）、announcement（公告）、manager_change（经理变更）、regulatory（监管）、market_event（市场事件） |
| `title` | string | 事件标题 |
| `date` | string | ISO 日期，必须在口径日及之前 |
| `impact_direction` | enum | 影响方向：bullish（利好）、bearish（利空）、neutral（中性） |
| `impact_score` | float | 影响程度 0.0-1.0，越高影响越大 |
| `confidence` | float | NLP 抽取置信度 0.0-1.0 |
| `affected_holdings` | string[] | 受影响的持仓股票代码列表 |
| `summary` | string | 一句话事件摘要 |

## 知识图谱分析（kg_analysis）

当 `--use-agents` 标志激活时，KG 模块产生以下洞察：

```json
{
  "fund_exposure": {
    "top_industries": [{"industry": "白酒", "weight_pct": 35.2}],
    "top_stocks": [{"code": "600519", "weight_pct": 9.5, "name": "贵州茅台"}],
    "concentration_risk": "high|medium|low"
  },
  "cross_fund_links": [
    {
      "fund_a": "000001",
      "fund_b": "110011",
      "shared_holdings": ["600519", "000858"],
      "overlap_pct": 45.0,
      "correlation_risk": "high|medium|low"
    }
  ],
  "impact_chains": [
    {
      "trigger": "白酒行业政策收紧",
      "affected_funds": ["000001", "110011"],
      "propagation_path": "行业政策 → 白酒板块 → 重仓白酒基金 → 净值下跌",
      "severity": "high|medium|low"
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `fund_exposure.top_industries` | array | 基金持仓前 N 大行业及权重 |
| `fund_exposure.concentration_risk` | enum | 持仓集中度风险等级 |
| `cross_fund_links` | array | 基金间交叉持股关系 |
| `cross_fund_links[].overlap_pct` | float | 重叠持仓占比较小基金的百分比 |
| `cross_fund_links[].correlation_risk` | enum | 交叉持股引发的相关性风险 |
| `impact_chains` | array | 外部事件对持仓基金的影响链 |
| `impact_chains[].propagation_path` | string | 影响传播路径描述 |
| `impact_chains[].severity` | enum | 影响严重程度 |

## 向后兼容

- 标准模式（未使用 `--use-agents`）下 `event_extraction` 和 `kg_analysis` 可能为 `null` 或缺失。
- `quant_baseline` 在标准模式下包含 `macro_score`/`meso_score`/`micro_score`，在 Agent 增强模式下扩展为 5 维度评分字段。
- Agent 决策前应检查 `schema_version` 和 `report_status`，确认输入来源。

Agent 不得绕过 evidence 临时补造事实。证据缺失时，应输出保守决策和复核项。
