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
├── cli.py              # 统一 CLI 入口
├── config/
│   ├── schema.py       # Pydantic 数据模型（YAML ↔ 对象）
│   ├── loader.py       # YAML 加载/校验/导入
│   ├── defaults.py     # 全局默认参数（含 QUANT_CONFIG）
│   └── shared.py       # 共享工具函数（报告/DCA 分界点）
├── engine/
│   ├── calendar.py     # AKShare 交易日历
│   ├── events.py       # 事件生成（BUY / CALIBRATE）
│   └── calculator.py   # 事件驱动计算引擎 + XIRR + 校准
├── analysis/
│   ├── scorer.py       # 三因子评分 + Sortino + HHI + 三层解耦输出
│   ├── holdings.py     # 持仓分析
│   ├── correlation.py  # 相关性矩阵
│   └── stress.py       # 情景压力测试（通过 --stress 显式启用）
├── data/
│   └── fetcher.py      # AKShare 数据采集
├── news/
│   ├── news_fetcher.py # 新闻抓取
│   └── sentiment.py    # 情绪分析（金融极性词典 + 指数衰减 + 原子关键词）
├── recommend/
│   └── engine.py       # 基金推荐引擎
├── output/
│   ├── report.py       # 证据稿 / Agent 最终报告渲染
│   ├── templates.py    # 报告模板与口径提示
│   └── validator.py    # 最终报告合同校验
├── db/
│   ├── models.py       # SQLAlchemy ORM
│   ├── database.py     # 数据库连接
│   └── storage.py      # 高层存储 API
└── ui/
    └── app.py          # Streamlit 交互界面
```

## 全局可调参数（QUANT_CONFIG）

| 参数 | 默认值 | 说明 | 环境变量覆盖 |
|------|--------|------|-------------|
| `SORTINO_MAR` | 0.025（2.5%） | 索提诺比率最低可接受收益率 | — |
| `NEWS_LAMBDA` | 0.200（半衰期 ~3.5天） | 舆情时间指数衰减系数 | — |

## 评分架构

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

`analyze` 子命令流程：

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

## License

MIT
