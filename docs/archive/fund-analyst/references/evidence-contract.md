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
- `kg_snapshot`：基金暴露和事件影响链快照。
- `news_evidence`：分类新闻、研究摘要和结构化事件。
- `score_evidence`：五维评分、regime、权重和 agent graph 状态。
- `strategy_evidence`：策略引擎建议与触发条件。

## 单基金字段

- `identity`：代码、名称、基金类型、数据完整度。
- `holding_metrics`：当前市值、成本、收益、pending、净值日期和结算证据。
- `quant_baseline`：宏观/中观/微观/总分和评分置信度。
- `factor_matrix`：可解释评分因子。
- `trend_evidence`：趋势证据，不是交易命令。
- `risk_constraints`：当前权重、pending、QDII、DCA 等约束。
- `news_evidence`：新闻数量、压缩摘要、覆盖评估、样本、口径日后观察和相关性任务。
- `strategy_advice`：（可选）该基金的状态机策略建议。
- `agent_score_context`：（可选）组合级 agent 结论和 graph 上下文。

## 增强扩展字段

当前 schema 固定为 `report_evidence.v2`，追加四个顶层扩展：

```json
{
  "kg_snapshot": {
    "fund_exposure": {
      "000001": {
        "industries": {"食品饮料": 35.2},
        "themes": {"消费": 35.2},
        "top_holdings": [{"code": "600519", "name": "贵州茅台", "weight": 9.5}]
      }
    },
    "impact_chains": {
      "evt_001": [
        {"from": "event:evt_001", "to": "industry:食品饮料", "edge_type": "impacts"}
      ]
    }
  },
  "news_evidence": {
    "000001": {
      "classified_news": [],
      "research_summaries": [],
      "extracted_events": []
    }
  },
  "score_evidence": {
    "000001": {
      "regime": "normal",
      "quant_score": {"score": 72.0, "confidence": 0.8},
      "fundamental_score": {"score": 68.0, "confidence": 0.7},
      "event_score": {"score": 55.0, "confidence": 0.6},
      "position_score": {"score": 70.0, "confidence": 0.8},
      "timing_score": {"score": 60.0, "confidence": 0.6},
      "weights_used": {"quant": 0.4, "fundamental": 0.2, "event": 0.15, "position": 0.15, "timing": 0.1},
      "agent_state": {
        "market_regime": "normal",
        "final_score": 66.0,
        "risk_assessment": {"risk_level": "medium"}
      }
    }
  },
  "strategy_evidence": {
    "000001": {
      "action": "hold",
      "confidence": 0.75,
      "risk_level": "medium",
      "reasons": ["综合评分中性，等待事件确认"],
      "trigger_events": ["行业政策变化后复核"],
      "position_suggestion": "维持当前仓位",
      "time_horizon": "medium"
    }
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `kg_snapshot.fund_exposure` | object | 每只基金的行业、主题和重仓暴露 |
| `kg_snapshot.impact_chains` | object | 事件 ID 到 KG 传播路径的映射 |
| `news_evidence[code].classified_news` | array/object | 6 层新闻分类结果 |
| `news_evidence[code].research_summaries` | array | 研究式新闻摘要 |
| `news_evidence[code].extracted_events` | array | 从保留新闻中抽出的结构化事件 |
| `score_evidence[code]` | object | ScoreEngine 产出的五维评分证据 |
| `score_evidence[code].agent_state` | object | LangGraph agent 节点产出的评分状态快照 |
| `strategy_evidence[code]` | object | StrategyEngine 或 StrategyAgent 产出的动作建议 |

## 向后兼容

- 四个增强扩展在对应引擎未运行时可能为空对象或缺失。
- `quant_baseline` 始终保留旧的 `macro_score`/`meso_score`/`micro_score` 桥接字段；五维评分写入 `score_evidence`。
- Agent 决策前应检查 `schema_version` 和 `report_status`，确认输入来源。

Agent 不得绕过 evidence 临时补造事实。证据缺失时，应输出保守决策和复核项。
