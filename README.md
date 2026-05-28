# Fund Agent

量化基金分析工具——纯量化特征计算引擎 + Agent 自主投研决策，核心输出基金诊断报告与投资建议。

## 功能

- **数据采集**：通过 AKShare 获取基金净值、业绩指标、持仓明细、新闻资讯
- **多因子评分证据**：宏观(20%) / 中观(30%) / 微观(50%) 三维度计算 `quant_baseline`，供 Agent 对账决策
- **高阶风险指标**：索提诺比率（Sortino）、赫芬达尔指数（HHI）、信息比率（IR）、詹森 Alpha、Beta 系数
- **持仓分析**：事件驱动计算引擎、XIRR 年化收益、校准平账、QDII T+2 结算支持
- **组合诊断**：相关性矩阵、情景压力测试（可选）、配置约束证据
- **新闻证据分析**：金融极性词典、指数时间衰减聚合、原子关键词召回、持仓覆盖度与口径日截断
- **基金推荐**：热点行业全市场筛选 + 行业/风格/收益风险多因子相似度 + 主题多样性约束
- **交互式 UI**：Streamlit Web 界面，持仓总览 / 基金详情 / 定投管理 / 增删基金
- **Agent 决策分层**：CLI 产出证据稿与 JSON → Agent 产出可对账决策 JSON → CLI 校验并渲染最终报告
- 🆕 **知识图谱分析**：基金→股票→行业→主题→事件的全链路关系图谱，NetworkX 内存图引擎
- 🆕 **向量语义搜索**：基于 embedding 的新闻相似度、历史模式匹配，Qdrant 向量数据库
- 🆕 **8阶段新闻流水线**：实体提取→定向检索→6层分类→多因子评分→向量重排→AI重排→研究摘要→事件抽取
- 🆕 **5维度混合评分**：量化因子(40%) + 基本面AI(20%) + 事件驱动(15%) + 持仓结构(15%) + 择时判断(10%)，权重随市场状态动态调整
- 🆕 **状态感知策略引擎**：WAIT/HOLD/ADD/REDUCE/STOP_LOSS 五状态机，根据市场波动、黑天鹅、趋势信号自动切换
- 🆕 **LangGraph 多智能体系统**：News/Quant/Research/Risk/Strategy 五大智能体协同研判
- 🆕 **多源新闻覆盖**：AKShare(A股) + Finnhub(美股QDII) + Tavily(AI补充搜索)

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化配置文件
python3 -m src.cli init -o fund-portfolio.yaml

# 编辑 fund-portfolio.yaml 填入你的持仓数据

# 生成证据稿（推荐和压力测试默认关闭；不滚动配置）
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --no-snapshot-after

# 如需把候选筛选与压力证据纳入本次 evidence
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --recommend --stress --no-snapshot-after

# Agent 读取 report.evidence.json 并产出 agent_decisions.json 后，渲染最终稿
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --agent-decisions agent_decisions.json --no-snapshot-after

# analyze 成功后默认滚动 fund-portfolio.yaml；如需单独滚动也可显式执行
python3 -m src.cli snapshot -c fund-portfolio.yaml

# 如本次只想生成报告、不更新配置
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --no-snapshot-after

# 🆕 新 AI 流水线（需要 API Key）
export FINNHUB_API_KEY="your_key"   # 美股新闻 (免费 60次/分)
export TAVILY_API_KEY="your_key"    # AI 补充搜索 (免费 1000次/月)
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --use-agents

# 或启动交互式界面
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

浏览器打开 `http://localhost:8501`。UI 中可以维护持仓、定投、生成报告，也可以手动执行定投滚动。

## 数据口径

- `fund-portfolio.yaml` 是当前持仓和策略的人工维护真源，保留 YAML 格式，便于手工审阅和小规模修改。
- SQLite 只保存基金元数据、净值缓存和分析快照，不作为当前持仓流水真源。
- `report.evidence.json` 是 Agent 决策的结构化输入；未提供 decisions 时的 `report.md` 明确标记为证据稿。
- `agent_decisions.json` 使用 `agent_decisions.v2` 合同，且口径日必须与本次 evidence 一致；CLI 只根据通过校验的 decisions 渲染最终 `report.md`。
- 报告口径日分界点为 **北京时间 22:22**（可设环境变量 `FUND_REPORT_CUTOFF_HOUR` / `FUND_REPORT_CUTOFF_MINUTE`）；22:22 前使用上一交易日口径。
- 定投数据刷新时间点为 **北京时间 10:00**（可设 `FUND_DCA_CUTOFF_HOUR` / `FUND_DCA_CUTOFF_MINUTE`）；10:00 前当日定投未计入。

## 技术架构

```
src/
├── cli.py                    # 统一 CLI 入口（支持 --use-agents 新流水线）
├── routes/                   # CLI 路由 (保留)
│   ├── cli_router.py         #   路由器
│   └── commands.py           #   命令定义
├── config/                   # Pydantic 数据模型 (保留)
│   ├── schema.py             #   YAML ↔ 对象
│   ├── loader.py             #   加载/校验/导入
│   ├── defaults.py           #   全局默认参数（含 QUANT_CONFIG）
│   └── shared.py             #   共享工具函数（报告/DCA 分界点）
├── engine/                   # 事件驱动计算引擎 (保留)
│   ├── calendar.py           #   AKShare 交易日历
│   ├── events.py             #   事件生成（BUY / CALIBRATE）
│   └── calculator.py         #   + XIRR + 校准
├── core/                     # 核心合约与工作流 (保留)
│   ├── contracts.py          #   数据合约定义
│   └── workflow.py           #   工作流定义
├── data/                     # 数据采集 (保留)
│   └── fetcher.py            #   AKShare 数据采集
├── db/                       # SQLAlchemy ORM + SQLite (保留)
│   ├── models.py             #   ORM 模型
│   ├── database.py           #   数据库连接
│   └── storage.py            #   高层存储 API
├── kg/                       # 🆕 知识图谱 (NetworkX)
│   ├── schema.py             #   节点/边类型定义
│   ├── graph.py              #   KnowledgeGraphBuilder
│   ├── industry_map.py       #   申万行业→投资主题映射
│   └── enrichment.py         #   事件注入图谱
├── vectorstore/              # 🆕 Qdrant 向量数据库
│   ├── collections.py        #   集合 Schema 定义
│   ├── embedding.py          #   EmbeddingPipeline
│   ├── client.py             #   Qdrant 客户端
│   └── search.py             #   余弦相似度 + 基金相似度
├── events/                   # 🆕 事件分类与提取
│   ├── taxonomy.py           #   事件类型层次结构
│   └── extractor.py          #   LLM/规则事件抽取
├── news/                     # 🆕 持仓驱动新闻流水线 (8阶段)
│   ├── news_pipeline.py      #   NewsPipeline 编排器
│   ├── retriever.py          #   持仓驱动新闻检索
│   ├── classifier.py         #   6层新闻分类
│   ├── scorer.py             #   多因子相关性评分 + 向量重排
│   ├── summarizer.py         #   研究报告式AI摘要
│   ├── schemas.py            #   数据模型
│   ├── finnhub_client.py     #   Finnhub 美股新闻 (免费60次/分)
│   ├── tavily_client.py      #   Tavily AI 搜索 (免费1000次/月)
│   ├── news_fetcher.py       #   新闻抓取 (保留)
│   ├── sentiment.py          #   情绪分析 (保留)
│   └── keyword_cache.py      #   关键词缓存 (保留)
├── analysis/                 # 分析模块
│   ├── scorer.py             #   三因子评分 (保留)
│   ├── holdings.py           #   持仓分析 (保留)
│   ├── correlation.py        #   相关性矩阵 (保留)
│   ├── stress.py             #   情景压力测试 (保留)
│   ├── factors.py            #   因子分析 (保留)
│   ├── metrics.py            #   业绩指标 (保留)
│   ├── portfolio_risk.py     #   组合风险 (保留)
│   ├── loader.py             #   数据加载 (保留)
│   └── scoring/              #   🆕 5维度AI+因子混合评分
│       ├── engine.py         #     ScoreEngine 编排器
│       ├── quant.py          #     QuantScore (数据驱动)
│       ├── fundamental.py    #     FundamentalScore (AI+KG)
│       ├── event_score.py    #     EventScore (新闻流水线+KG)
│       ├── position.py       #     PositionScore (持仓结构)
│       ├── timing.py         #     TimingScore (择时判断)
│       ├── regime.py         #     市场状态检测
│       ├── factors.py        #     动态因子权重
│       ├── types.py          #     ScoreComponent/MarketRegime
│       ├── macro.py          #     宏观评分 (保留)
│       ├── meso.py           #     中观评分 (保留)
│       └── micro.py          #     微观评分 (保留)
├── recommend/                # 基金推荐引擎 (保留)
│   └── engine.py             #   推荐引擎
├── strategy/                 # 🆕 策略引擎 (状态机)
│   ├── engine.py             #   StrategyEngine
│   ├── state_machine.py      #   状态转换 (WAIT→HOLD→ADD→REDUCE→STOP_LOSS)
│   ├── advisor.py            #   StrategyAdvisor
│   ├── stop_logic.py         #   状态感知止损/止盈
│   └── schemas.py            #   StrategyAction/StrategyAdvice
├── agents/                   # 🆕 LangGraph 多智能体
│   ├── state.py              #   FundResearchState
│   ├── supervisor.py         #   路由逻辑
│   ├── orchestrator.py       #   编排器 (保留)
│   ├── protocols.py          #   协议定义 (保留)
│   ├── summary.py            #   摘要生成 (保留)
│   └── graphs/               #   5个专用智能体节点
│       ├── supervisor.py     #     监督路由
│       ├── news_agent.py     #     新闻智能体
│       ├── quant_agent.py    #     量化智能体
│       ├── research_agent.py #     研究智能体
│       ├── risk_agent.py     #     风险智能体
│       └── strategy_agent.py #     策略智能体
├── forecast/                 # 预测引擎 (保留)
│   └── engine.py             #   预测引擎
├── tools/                    # 工具注册表 (保留)
│   ├── registry.py           #   工具注册
│   └── evidence_tools.py     #   证据工具
├── prompts/                  # Prompt 加载器 (保留)
│   └── loader.py             #   Prompt 加载
├── output/                   # 报告渲染 + 合同校验 (保留)
│   ├── report.py             #   证据稿 / Agent 最终报告渲染
│   ├── templates.py          #   报告模板与口径提示
│   └── validator.py          #   最终报告合同校验
├── services/                 # 服务层 (保留)
│   ├── news_service.py       #   新闻服务
│   ├── portfolio_service.py  #   组合服务
│   ├── report_service.py     #   报告服务
│   ├── scoring_service.py    #   评分服务
│   ├── snapshot_service.py   #   快照服务
│   └── workflow_context.py   #   工作流上下文
└── ui/                       # Streamlit 交互界面 (保留)
    └── app.py                #   UI 入口
```

## 全局可调参数（QUANT_CONFIG）

| 参数 | 默认值 | 说明 | 环境变量覆盖 |
|------|--------|------|-------------|
| `SORTINO_MAR` | 0.025（2.5%） | 索提诺比率最低可接受收益率 | — |
| `NEWS_LAMBDA` | 0.200（半衰期 ~3.5天） | 舆情时间指数衰减系数 | — |

## 评分架构

### 🆕 5维度混合评分（新流水线 `--use-agents`）

新流水线采用 AI + 因子混合评分引擎，权重随市场状态动态调整：

```
ScoreEngine
├── QuantScore (40%)         # 数据驱动：多因子量化模型 + 高阶指标
│   ├── Sortino / Sharpe     #   风险调整收益
│   ├── HHI                  #   持仓集中度
│   ├── Jensen Alpha / Beta  #   超额收益 / 系统风险
│   ├── IR / MDD             #   信息比率 / 最大回撤
│   └── Momentum / Vol       #   动量 / 波动率
├── FundamentalScore (20%)   # AI+KG 驱动：基本面分析
│   ├── macro.py             #   宏观经济评分 (保留)
│   ├── meso.py              #   中观行业评分 (保留)
│   └── micro.py             #   微观基金评分 (保留)
├── EventScore (15%)         # 新闻流水线 + KG 注入
│   └── 持仓驱动事件提取 → 影响路径传播
├── PositionScore (15%)      # 持仓结构分析
│   └── 行业分布 / 集中度 / 风格暴露
├── TimingScore (10%)        # 择时判断
│   └── 趋势信号 / 估值分位数 / 市场情绪
└── MarketRegime             # 市场状态检测
    └── 牛/熊/震荡 → 动态权重调整
```

### 旧流水线评分架构（保留，`analyze` 无 `--use-agents` 时使用）

```
report.evidence.json
├── quant_baseline     # 引擎计算的基准分（宏观/中观/微观）
├── trend_evidence     # 趋势方向证据，不自动产生动作
├── risk_constraints   # 仓位、pending、结算和组合风险约束
├── news_evidence      # 新闻样本、覆盖限制和口径日后观察
├── workflow_evidence  # 定投与全持仓结算状态
└── recommendation_evidence # 仅供 Agent 复核的候选证据

agent_decisions.json
├── agent_adjustments  # Agent 策略修正分（各维度 [-10, +10]）
├── final_scores       # 可与基准分和修正值对账的最终分
├── final_action       # Agent 最终动作
└── rationale/triggers # 可审计理由与复核条件

feature_matrix         # 连续特征矩阵
├── hhi_index          # 赫芬达尔持仓集中度
├── jensen_alpha       # 詹森 Alpha
├── sortino_ratio      # 索提诺比率
├── information_ratio  # 信息比率
├── beta               # Beta 系数
├── max_drawdown_3y_pct
├── annual_volatility
└── sharpe_1y
```

## 分析流水线

### 旧流水线（`analyze`，保留）

1. 加载并校验 `fund-portfolio.yaml`，导入持仓到数据库
2. 同步基金基础元数据到 SQLite
3. 按持仓基金逐个采集 AKShare 数据（净值/业绩/持仓/行业）
4. 以报告口径日（22:22 分界）计算持仓
5. 事件驱动计算份额、pending、XIRR
6. 量化基准评分 + 高阶指标（Sortino/HHI/Alpha/IR/Beta）
7. 检查新闻关键词缓存（14 天有效）；无效时输出 `report.md.news_keywords_request.json` 等待 Agent 生成缓存
8. 口径日截断、去重、新闻覆盖评估 + 指数时间衰减辅助信号
9. 相关性矩阵；压力测试和候选筛选分别通过 `--stress`、`--recommend` 启用
10. 输出 `report.evidence.json` 和显著标记为证据稿的 `report.md`
11. 默认滚动定投记录并写回 YAML（可用 `--no-snapshot-after` 关闭）
12. Agent 读取 evidence，生成 `agent_decisions.v2`；CLI 校验日期、覆盖和评分对账后渲染最终报告

### 🆕 新流水线（`analyze --use-agents`）

使用 LangGraph 多智能体系统，全链路 AI 驱动分析：

1. 加载配置、同步元数据、采集数据（同旧流水线 Step 1-5）
2. 构建知识图谱：基金→持仓→行业→主题→事件的全链路关系
3. Embedding 向量化：持仓特征、历史模式编码到 Qdrant
4. 8阶段新闻流水线：实体提取→定向检索→分类→多因子评分→向量重排→AI重排→摘要→事件抽取
5. 5维度 AI+因子混合评分：量化(40%) + 基本面AI(20%) + 事件(15%) + 持仓(15%) + 择时(10%)
6. 策略引擎状态机决策：根据市场状态 + 持仓结构 + 评分 + 事件信号输出策略建议
7. LangGraph 五大智能体协同：News/Quant/Research/Risk/Strategy Agent 并行研判
8. 输出 `report.md` 最终报告和 `report.evidence.json` 证据文件

## License

MIT
