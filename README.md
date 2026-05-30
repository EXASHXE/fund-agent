# AI Financial Research OS

> Research OS beta path — 宿主可注入 MCP 能力、证据图驱动决策、行动账本输出。

## 概述

一个由 LLM Agent 调用的基金投研操作系统 beta path。宿主注入 MCP 能力（资讯、搜索、舆情），Research OS 通过 **Skill** 编排纯数学工具、知识图谱（KG）、基础设施适配和证据图引擎，产出结构化 `FinalThesis`、决策合约与行动账本。当前不是 production-ready 运行时；重点是契约、边界和可审计闭环。

**核心设计原则：**
- **纯工具无副作用** — `src/tools/` 中的数学函数（Sortino / HHI / Sharpe / XIRR）无 IO、无网络、无 LLM，可独立验证
- **知识图谱冷启动** — 基金→股票→行业→主题→事件全链路关系，NetworkX 内存图引擎，可增量刷新
- **证据驱动决策** — 所有主动投资决策追溯至真实 `EvidenceItem`，HardEvidence 置信度恒为 1.0，支持冲突检测与 Hybrid 升级
- **结构化 Research OS 闭环** — Planner → Skill execution → EvidenceGraph compile → Critic → DecisionEngine → ExecutionLedger，Critic 未通过则重试并在预算耗尽时返回 EXHAUSTED

## 架构

```
fund-agent/
├── skills/                    # 4 个 AI-native Skill
│   ├── fund_analysis/         #   CIO 级战略投研，多维度评分，组合再平衡
│   ├── news_research/         #   持仓驱动新闻检索，6 层分类，多因子评分
│   ├── sentiment_analysis/    #   舆情极性/强度/时间衰减/信源加权
│   └── thesis_generation/     #   投资命题生成，证据链追溯，决策合约输出
├── src/                       # ★ Research OS 主路径
│   ├── core/                  #   研究编排核心
│   │   ├── research_os.py     #     主循环：KG→Plan→Skills→Evidence→Critic→Decision→Ledger
│   │   ├── planner.py         #     KG 驱动的 Plan/PlanStep 生成
│   │   ├── critic.py          #     6 维度结构化评审 (PASS/RETRY/FAIL/EXHAUSTED)
│   │   ├── decision_engine.py #     合约强制决策引擎
│   │   ├── skill_registry.py  #     Skill 注册、MCP adapter 注入与运行
│   │   └── ledger.py          #     ExecutionLedger 构建
│   ├── schemas/               #   类型化合约
│   │   ├── evidence.py        #     EvidenceItem (evidence-contract.v2)
│   │   ├── decision.py        #     Decision / ActionType (decision-contract.v2)
│   │   ├── evidence_graph.py  #     EvidenceGraph (去重/冲突检测/Hybrid 升级)
│   │   ├── skill.py           #     SkillInput / SkillOutput runtime contract
│   │   ├── research_task.py   #     ResearchTask (新入口)
│   │   └── report.py          #     FinalThesis
│   ├── skills_runtime/        #   Adapter-only runtime Skill handlers
│   ├── graph/                 #   KnowledgeGraph (唯一权威实现)
│   │   ├── builder.py         #     KnowledgeGraphBuilder
│   │   ├── schema.py          #     节点/边类型定义 (7 entity, 10 edge types)
│   │   ├── knowledge_graph.py #     KnowledgeGraph 包装类
│   │   ├── queries.py         #     get_entity_chain / query_exposure / expand_theme
│   │   ├── cache.py           #     KG 缓存
│   │   ├── industry_map.py    #     申万行业→投资主题映射
│   │   ├── enrichment.py      #     事件注入图谱
│   │   └── diff.py            #     图差异对比
│   ├── tools/                 #   纯函数数学工具（无 IO/无网络/无 LLM）
│   │   ├── quant/             #     Sharpe/Sortino/MaxDD/Vol/HHI
│   │   ├── ledger/            #     execution_amount/settlement/DCA
│   │   ├── evidence/          #     builders/validators
│   │   └── adapters/          #     Host-native MCP adapter 抽象（无供应商 SDK）
│   ├── infra/                 #   基础设施层
│   │   ├── config/            #     Pydantic 配置
│   │   ├── data/              #     AKShare 数据采集
│   │   ├── persistence/       #     SQLAlchemy ORM + SQLite
│   │   └── vectorstore/       #     Qdrant 向量数据库
│   ├── workflows/             #   薄编排入口
│   │   └── research_os.py     #     薄封装 → src.core.research_os
│   └── cli.py                 #   legacy compatibility shim → legacy/cli.py
├── legacy/                    # ★ 旧系统（保留兼容）
│   ├── cli.py                 #   旧 CLI analyze 入口
│   ├── workflows/             #   旧 workflow 编排
│   ├── analysis/              #   旧评分引擎 (Quant/Fundamental/Event/Position/Timing)
│   ├── news/                  #   旧新闻流水线
│   ├── strategy/              #   旧状态机策略引擎
│   ├── agents/                #   旧 LangGraph 多智能体
│   ├── engine/                #   旧事件驱动计算引擎
│   ├── services/              #   旧服务层
│   ├── output/                #   旧报告渲染
│   ├── recommend/             #   旧推荐引擎
│   ├── ui/                    #   Streamlit UI
│   ├── routes/                #   CLI 路由
│   ├── prompts/               #   LLM prompts
│   ├── events/                #   事件分类
│   ├── forecast/              #   预测引擎
│   └── deprecated/            #   已废弃代码
└── docs/contracts/            # v2 合约文档
    ├── evidence-contract.v2.md
    └── decision-contract.v2.md
```

**Architecture boundary: `src/` = new Research OS beta path. `legacy/` = old CLI/report/news/recommend/ui system.**  `src/core/` never imports `legacy/`.

## 目录职责

- `src/core/`: Planner / Critic / DecisionEngine / LedgerBuilder / SkillRegistry / Research OS runtime
- `src/schemas/`: ResearchTask、SkillInput、SkillOutput、EvidenceItem、EvidenceGraph、Decision、ExecutionLedger、FinalThesis contracts
- `src/skills_runtime/`: adapter-only Skill handlers，Skill 只返回 evidence/artifacts/warnings/errors
- `src/graph/`: KnowledgeGraph canonical implementation and query helpers
- `src/tools/`: quant / ledger / evidence / adapters，保持无 LLM、无网络、无供应商 SDK
- `src/infra/`: config / data / persistence / vectorstore 的真实实现
- `legacy/`: old CLI/report/news/recommend/ui path，仅作 compatibility/reference

## Research OS Path (New)

The new Research OS architecture is the primary structured path:

```
ResearchTask → Planner → KnowledgeGraph query → SkillInput → SkillRegistry → SkillOutput → Evidence compile → Critic → DecisionEngine → ExecutionLedger
```

**Key differences from legacy path:**

| Aspect | Legacy (`python -m src.cli analyze`) | Research OS (`src.core.research_os` / `src.workflows.research_os`) |
|--------|---------------------------|--------------------------------------|
| Entry | CLI command | `ResearchTask` typed dataclass |
| Planning | None | Planner queries KG then generates PlanSteps |
| Evidence | Report JSON field | EvidenceGraph (dedup, conflict, hybrid) |
| Review | None | Critic with PASS/RETRY/FAIL/EXHAUSTED |
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

`python -m src.cli analyze` is a legacy compatibility path backed by
`legacy/`. New integrations should use `src.core.research_os.run_research_task`
or the thin `src.workflows.research_os` Research OS path.

## Skill Runtime 能力矩阵

| Runtime Skill | MCP capability plan | 输出边界 |
|---------------|---------------------|----------|
| `FundAnalysisSkill` / `QuantRiskAnalysis` | 无；只用本地纯工具 | `HardEvidence`，`confidence_weight=1.0` |
| `NewsResearchSkill` | `web_search`、`financial_news`，`company_filings` 可作为宿主扩展能力 | `SoftEvidence` + artifacts/errors |
| `SentimentAnalysisSkill` | `social_sentiment`，`trend_radar`/`reddit_search` 可作为宿主扩展能力 | `SoftEvidence` + artifacts/errors |
| `ThesisGenerationSkill` | 无；只依赖 EvidenceGraph 上下文 | `thesis_draft` artifact，不生成正式 `Decision` |

`Planner` 只产出 `PlanStep.required_mcp_capabilities`，不调用 MCP、不访问网络、不生成 Decision。`ResearchOS` 将 `PlanStep` 转为 `SkillInput`，经 `SkillRegistry` 注入 `MCPHostAdapter` 后执行。`SkillOutput` 是 Skill 的唯一返回通道。

## 调用模型

### LLM Agent 调用（主要方式）

```
Host (Claude / GPT / Gemini / LLM ...) 加载 fund-analyst Skill
  → Skill 声明所需 MCP 能力
    → Host 注入能力实现（provider 由宿主负责）
      → Skill 通过 ToolRegistry 编排纯数学工具 + KG 查询 + MCP adapter boundary
        → Research OS 闭环执行：Planner → Skills → EvidenceGraph compile → Critic → DecisionEngine → Ledger
          → 产出 FinalThesis + EvidenceGraph compile report + Decision/ExecutionLedger
```

项目内只声明 `src.tools.adapters.mcp` 的 host-native adapter 抽象，不硬编码 Tavily/Finnhub/Exa/Firecrawl/Reddit SDK，也不在 Skill 内写供应商 API 调用。

### CLI 调用（本地开发/测试）

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md
```

CLI 是 legacy compatibility path，仅用于旧 analyze/report/news/recommend/ui 系统。本轮新系统入口是 `src.core.research_os.run_research_task` 和 `src.workflows.research_os`。

## 数据层

- **持仓真源**：`fund-portfolio.yaml` — YAML 格式，人工维护，便于审阅
- **缓存层**：SQLite — 基金元数据、净值缓存、分析快照
- **向量存储**：Qdrant adapter — embedding 相似度搜索、历史模式匹配
- **知识图谱**：NetworkX 内存图 — 基金→持仓→行业→主题→事件全链路
- **外部能力**：新 Research OS 通过 host MCP capability 注入；旧系统的数据/API 依赖保留在 `legacy/` compatibility path
- **报告口径日**：北京时间 22:22（可设 `FUND_REPORT_CUTOFF_HOUR` / `FUND_REPORT_CUTOFF_MINUTE`）
- **定投刷新点**：北京时间 10:00（可设 `FUND_DCA_CUTOFF_HOUR` / `FUND_DCA_CUTOFF_MINUTE`）

## 评分引擎

ScoreEngine 采用 5 维度 AI+因子混合评分，权重随市场状态动态调整（`legacy/analysis/scoring/`）：

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
| `Decision` | decision-contract.v2 | 10 字段：decision_id, action, execution_amount, rationale_anchor, trigger_conditions, invalidating_conditions, time_horizon, risk_budget, audit_trail, version | 主动决策须引用真实 evidence_id；WAIT/HOLD/PAUSE_DCA 可在说明证据不足或被 Critic 阻断时空 anchor；BUY/SELL/INCREASE/REDUCE 须有执行金额 |
| `EvidenceGraph` | — | items{id→EvidenceItem}, edges[(from, to)] | 支持验证、拒绝无效证据、去重、冲突检测、Soft→Hybrid 升级、置信度聚合 |
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
# Provider credentials are host/legacy concerns. The new Research OS path
# receives MCP providers through MCPHostAdapter injection.
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
