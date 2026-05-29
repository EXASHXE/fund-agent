# AI Financial Research OS

> 宿主可注入的 AI-native Skill Pack — LLM 主导投研、MCP 能力注入、证据图驱动决策、行动账本输出。

## 概述

一个由 LLM Agent 调用的基金投研操作系统。宿主注入 MCP 能力（资讯、搜索、舆情），Agent 通过 **Skill** 编排纯数学工具、知识图谱（KG）、向量数据库（Qdrant）和证据图引擎，产出结构化投研报告与可执行投资决策。

**核心设计原则：**
- **纯工具无副作用** — `src/tools/` 中的数学函数（Sortino / HHI / Sharpe / XIRR）无 IO、无网络、无 LLM，可独立验证
- **知识图谱冷启动** — 基金→股票→行业→主题→事件全链路关系，NetworkX 内存图引擎，可增量刷新
- **证据驱动决策** — 所有投资决策追溯至 `EvidenceItem`，HardEvidence 置信度恒为 1.0，支持冲突检测与 Hybrid 升级
- **8 节点反思回路** — Planner → News → Quant → Risk → Research → Critic → Strategy → Ledger，Critic 未通过则回退 Planner（最多 3 轮）

## 架构

```
fund-agent/
├── skills/                    # 4 个 AI-native Skill
│   ├── fund_analysis/         #   CIO 级战略投研，多维度评分，组合再平衡
│   ├── news_research/         #   持仓驱动新闻检索，6 层分类，多因子评分
│   ├── sentiment_analysis/    #   舆情极性/强度/时间衰减/信源加权
│   └── thesis_generation/     #   投资命题生成，证据链追溯，决策合约输出
├── src/
│   ├── schemas/               # 类型化合约
│   │   ├── evidence.py        #   EvidenceItem (evidence-contract.v2)
│   │   ├── decision.py        #   Decision / ActionType (decision-contract.v2)
│   │   └── evidence_graph.py  #   EvidenceGraph — 统一证据存储/去重/冲突检测
│   ├── tools/                 # 纯函数数学工具（无 IO/无网络/无 LLM）
│   │   ├── registry.py        #   ToolRegistry — 工具注册与绑定
│   │   └── evidence_tools.py  #   只读证据查询工具
│   ├── kg/                    # 知识图谱（NetworkX 内存图）
│   │   ├── schema.py          #   节点/边类型定义
│   │   ├── graph.py           #   KnowledgeGraphBuilder
│   │   ├── industry_map.py    #   申万行业→投资主题映射
│   │   └── enrichment.py      #   事件注入图谱
│   ├── agents/                # 8 节点 LangGraph 多智能体
│   │   ├── state.py           #   FundResearchState
│   │   ├── supervisor.py      #   路由逻辑
│   │   └── graphs/            #   8 个专用节点
│   │       ├── planner_agent.py   #   研究计划生成
│   │       ├── news_agent.py      #   新闻研究
│   │       ├── quant_agent.py     #   量化分析
│   │       ├── risk_agent.py      #   风险评估
│   │       ├── research_agent.py  #   深度研究
│   │       ├── critic_agent.py    #   评审（含迭代回路）
│   │       ├── strategy_agent.py  #   策略建议
│   │       └── ledger_node.py     #   ExecutionLedger 输出
│   ├── vectorstore/           # Qdrant 向量数据库
│   │   ├── client.py          #   Qdrant 客户端
│   │   ├── embedding.py       #   EmbeddingPipeline
│   │   ├── search.py          #   余弦相似度 + 基金相似度
│   │   └── collections.py     #   集合 Schema
│   ├── news/                  # 持仓驱动新闻流水线（8 阶段）
│   │   ├── news_pipeline.py   #   NewsPipeline 编排器
│   │   ├── retriever.py       #   持仓驱动新闻检索
│   │   ├── classifier.py      #   6 层新闻分类
│   │   ├── scorer.py          #   多因子相关性评分 + 向量重排
│   │   ├── summarizer.py      #   研究报告式 AI 摘要
│   │   ├── finnhub_client.py  #   Finnhub 美股新闻（免费 60 次/分）
│   │   └── tavily_client.py   #   Tavily AI 搜索（免费 1000 次/月）
│   ├── core/                  # 工作流编排与合约校验
│   │   ├── workflow.py        #   核心工作流实现
│   │   └── contracts.py       #   数据合约定义
│   ├── workflows/             # 薄编排入口（不承载业务逻辑）
│   │   └── analyze.py         #   分析工作流入口
│   ├── config/                # Pydantic 数据模型
│   ├── engine/                # 事件驱动计算引擎（XIRR / BUY / CALIBRATE）
│   ├── data/                  # AKShare 数据采集
│   ├── db/                    # SQLAlchemy ORM + SQLite
│   ├── analysis/scoring/      # 5 维度 AI+因子混合评分引擎
│   ├── strategy/              # 状态机策略引擎（WAIT→HOLD→ADD→REDUCE→STOP_LOSS）
│   ├── services/              # 服务层
│   ├── output/                # 报告渲染 + 合同校验
│   ├── ui/                    # Streamlit 交互界面
│   └── deprecated/            # 旧流水线保留代码（不影响主线）
```

## Research OS Path (New)

The new Research OS architecture provides an alternative, structured path:

```
ResearchTask → Planner → KnowledgeGraph query → Skill execution → Evidence compile → Critic → DecisionEngine → ExecutionLedger
```

**Key differences from legacy path:**

| Aspect | Legacy (`src.cli analyze`) | Research OS (`src.core.research_os`) |
|--------|---------------------------|--------------------------------------|
| Entry | CLI command | `ResearchTask` typed dataclass |
| Planning | None | Planner queries KG then generates PlanSteps |
| Evidence | Report JSON field | EvidenceGraph (dedup, conflict, hybrid) |
| Review | None | Critic with PASS/RETRY/FAIL |
| Decision | Basic recommendation | DecisionContract v2 (execution_amount, rationale_anchor, trigger/invalidating_conditions) |
| Auditing | None | ExecutionLedger with audit trail |

**Usage:**
```python
from src.schemas.research_task import ResearchTask
from src.core.research_os import run_research_task

task = ResearchTask(
    task_id="my-analysis",
    fund_universe=["110011", "005827"],
    objective="quarterly review",
    risk_profile="moderate",
)
result = run_research_task(task)
# result contains: decision, ledger, evidence, critique status
```

The legacy path continues to work unchanged. Both paths coexist.

## Skill 能力矩阵

| Skill | MCP 依赖 | 核心能力 |
|-------|----------|----------|
| **fund-analysis** | TrendRadar, Tavily, Exa, Firecrawl, Finnhub, Reddit | CIO 级战略投研，多维度评分（宏观 20%、中观 30%、微观 50%），组合再平衡 |
| **news-research** | Finnhub, Tavily, Exa, Firecrawl | 持仓驱动新闻检索，6 层分类，多因子相关性评分 |
| **sentiment-analysis** | Reddit, TrendRadar | 金融词典极性分析，指数时间衰减，信源加权聚合 |
| **thesis-generation** | 全部 6 个 MCP | 投资命题生成，EvidenceItem → Decision 映射，ExecutionLedger 输出 |

## 调用模型

### LLM Agent 调用（主要方式）

```
Host (Claude / GPT / Gemini / LLM ...) 加载 fund-analyst Skill
  → Skill 声明所需 MCP 能力
    → Host 注入 TrendRadar / Tavily / Finnhub / Exa / Firecrawl / Reddit
      → Skill 通过 ToolRegistry 编排纯数学工具 + KG 查询 + MCP adapter
        → 8 节点 LangGraph 依次执行（含 Critic 反思回路）
          → 产出 EvidenceGraph + Decision[] + ExecutionLedger
```

### CLI 调用（本地开发/测试）

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md
```

CLI 是薄封装，仅用于本地调试。核心业务逻辑全部在 `skills/`、`src/tools/`、`src/agents/` 中。

## 数据层

- **持仓真源**：`fund-portfolio.yaml` — YAML 格式，人工维护，便于审阅
- **缓存层**：SQLite — 基金元数据、净值缓存、分析快照
- **向量存储**：Qdrant — embedding 相似度搜索、历史模式匹配
- **知识图谱**：NetworkX 内存图 — 基金→持仓→行业→主题→事件全链路
- **数据源**：AKShare（A 股） + Finnhub（美股 QDII） + Tavily（AI 补充搜索）
- **报告口径日**：北京时间 22:22（可设 `FUND_REPORT_CUTOFF_HOUR` / `FUND_REPORT_CUTOFF_MINUTE`）
- **定投刷新点**：北京时间 10:00（可设 `FUND_DCA_CUTOFF_HOUR` / `FUND_DCA_CUTOFF_MINUTE`）

## 评分引擎

ScoreEngine 采用 5 维度 AI+因子混合评分，权重随市场状态动态调整（`src/analysis/scoring/`）：

```
ScoreEngine
├── QuantScore (40%)         # 数据驱动：多因子量化模型 + 高阶指标
│   ├── Sortino / Sharpe     #   风险调整收益
│   ├── HHI                  #   持仓集中度
│   ├── Jensen Alpha / Beta  #   超额收益 / 系统风险
│   ├── IR / MDD             #   信息比率 / 最大回撤
│   └── Momentum / Vol       #   动量 / 波动率
├── FundamentalScore (20%)   # AI+KG 驱动：宏观/中观/微观基本面
├── EventScore (15%)         # 新闻流水线 + KG 事件影响路径
├── PositionScore (15%)      # 持仓结构分析（行业分布/集中度/风格暴露）
├── TimingScore (10%)        # 择时判断（趋势信号/估值分位数/市场情绪）
└── MarketRegime             # 市场状态检测 → 动态权重调整
```

## 合约体系

| 合约 | 版本 | 核心字段 | 约束 |
|------|------|---------|------|
| `EvidenceItem` | evidence-contract.v2 | 11 字段：evidence_id, evidence_type, source_type, timestamp, related_entities, claim, value, confidence_weight, direction, version, provenance | HardEvidence 置信度恒为 1.0；SoftEvidence 限 [0.1, 0.9] |
| `Decision` | decision-contract.v2 | 10 字段：decision_id, action, execution_amount, rationale_anchor, trigger_conditions, invalidating_conditions, time_horizon, risk_budget, audit_trail, version | 至少引用一个 evidence_id；BUY/SELL/INCREASE/REDUCE 须有执行金额 |
| `EvidenceGraph` | — | items{id→EvidenceItem}, edges[(from, to)] | 支持去重、冲突检测、Soft→Hybrid 升级 |
| `ExecutionLedger` | — | decisions: list[Decision], summary | 可审计决策账本 |

## 开发

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/ -v    # 971 个测试
PYTHONPATH=. python -m pytest tests/test_kg_*.py -v    # KG 专用测试
PYTHONPATH=. python -m pytest tests/test_skill_*.py -v # Skill 专用测试
PYTHONPATH=. python -m pytest tests/test_schemas_*.py -v # 合约测试
```

## 环境变量

```bash
export FINNHUB_API_KEY="your_key"   # 美股新闻（免费 60 次/分）
export TAVILY_API_KEY="your_key"    # AI 补充搜索（免费 1000 次/月）
# 可选
export FUND_REPORT_CUTOFF_HOUR=22
export FUND_DCA_CUTOFF_HOUR=10
```

## 全局可调参数（QUANT_CONFIG）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SORTINO_MAR` | 0.025（2.5%） | 索提诺比率最低可接受收益率 |
| `NEWS_LAMBDA` | 0.200（半衰期 ~3.5 天） | 舆情时间指数衰减系数 |

## License

MIT
