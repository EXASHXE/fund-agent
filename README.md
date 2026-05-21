# Fund Agent

量化基金分析工具——纯量化特征计算引擎 + Agent 自主投研决策，核心输出基金诊断报告与投资建议。

## 功能

- **数据采集**：通过 AKShare 获取基金净值、业绩指标、持仓明细、新闻资讯
- **多因子评分**：宏观(20%) / 中观(30%) / 微观(50%) 三维度纯量化打分，输出三层解耦评分矩阵（quant_baseline + agent_overlay + final_score）
- **高阶风险指标**：索提诺比率（Sortino）、赫芬达尔指数（HHI）、信息比率（IR）、詹森 Alpha、Beta 系数
- **持仓分析**：事件驱动计算引擎、XIRR 年化收益、校准平账、QDII T+2 结算支持
- **组合诊断**：相关性矩阵、情景压力测试（可选）、再平衡方案
- **新闻情绪分析**：金融极性词典替代 SnowNLP、指数时间衰减加权聚合（λ 可调）、原子化关键词白名单匹配
- **基金推荐**：热点行业全市场筛选 + 行业/风格/收益风险多因子相似度 + 主题多样性约束
- **交互式 UI**：Streamlit Web 界面，持仓总览 / 基金详情 / 定投管理 / 增删基金
- **Agent 自主执笔**：CLI 产出纯数据模板 → Agent 读取并填充全部分析文本，无硬编码定性内容

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化配置文件
python3 -m src.cli init -o fund-portfolio.yaml

# 编辑 fund-portfolio.yaml 填入你的持仓数据

# 运行完整分析（默认不改写持仓配置，跳过推荐和压力测试加速）
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-recommend --skip-stress

# 如需完整分析含推荐
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

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
- Markdown 报告是输出产物——CLI 产出含量化表格+AGENT 占位符的模板，由 Agent 填充分析文本后成为最终报告。
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
│   └── stress.py       # 情景压力测试（可通过 --skip-stress 跳过）
├── data/
│   └── fetcher.py      # AKShare 数据采集
├── news/
│   ├── news_fetcher.py # 新闻抓取
│   └── sentiment.py    # 情绪分析（金融极性词典 + 指数衰减 + 原子关键词）
├── recommend/
│   └── engine.py       # 基金推荐引擎
├── output/
│   ├── report.py       # Markdown 报告生成（纯数据+AGENT插槽，无硬编码分析文本）
│   └── templates.py    # 报告模板
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
scoring_matrix
├── quant_baseline     # 纯量化基准分（宏观/中观/微观，满分100）
├── agent_overlay      # Agent 策略修正分（各维度 [-10, +10]）
│   ├── macro_adjustment
│   ├── meso_adjustment
│   ├── micro_adjustment
│   └── overlay_rationale
└── final_score        # 最终综合分 = baseline + overlay

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
6. 三层解耦评分 + 高阶指标（Sortino/HHI/Alpha/IR/Beta）
7. 检查新闻关键词缓存（14 天有效）；无效时输出 `report.md.news_keywords_request.json` 等待 Agent 生成缓存
8. 金融极性词典情绪分析 + 指数时间衰减聚合
9. 相关性矩阵 + 压力测试（可通过 `--skip-stress` 跳过）+ 基金推荐（可通过 `--skip-recommend` 跳过）
10. 生成 report.md 模板（纯量化数据 + AGENT 占位符，无硬编码分析文本）
11. 默认滚动定投记录并写回 YAML（可用 `--no-snapshot-after` 关闭）
12. Agent 读取模板，逐一填充所有 AGENT 占位符，grep 自检零残留后输出最终报告

## License

MIT
