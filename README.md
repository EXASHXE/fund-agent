# Fund Agent

量化基金分析工具，核心输出基金诊断报告与投资建议。

## 功能

- **数据采集**：通过 AKShare 获取基金净值、业绩指标、持仓明细、新闻资讯
- **多因子评分**：宏观(20%) / 中观(30%) / 微观(50%) 三维度打分，输出操作建议
- **持仓分析**：事件驱动计算引擎、XIRR 年化收益、校准平账、QDII T+2 结算支持
- **组合诊断**：相关性矩阵、情景压力测试、行业集中度、再平衡方案
- **新闻情绪分析**：基金相关新闻抓取 + 中文情绪分析 + 新闻-净值相关性
- **基金推荐**：热点行业全市场筛选 + 行业/风格/收益风险多因子相似度 + 主题多样性约束
- **交互式 UI**：Streamlit Web 界面，持仓总览 / 基金详情 / 定投管理 / 增删基金

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化配置文件
python3 -m src.cli init -o fund-portfolio.yaml

# 编辑 fund-portfolio.yaml 填入你的持仓数据

# 运行完整分析（默认不改写持仓配置）
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# 如需在报告生成后滚动定投记录，再显式执行
python3 -m src.cli snapshot -c fund-portfolio.yaml

# 或在 analyze 成功后自动滚动
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --snapshot-after

# 或启动交互式界面
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

浏览器打开 `http://localhost:8501`。UI 中可以维护持仓、定投、生成报告，也可以手动执行定投滚动。

## 数据口径

- `fund-portfolio.yaml` 是当前持仓和策略的人工维护真源，保留 YAML 格式，便于手工审阅和小规模修改。
- SQLite 只保存基金元数据、净值缓存和分析快照，不作为当前持仓流水真源。
- Markdown 报告是输出产物，不回写持仓。
- 定投滚动不会在默认分析前自动执行，只通过 `snapshot` 或 `analyze --snapshot-after` 写回 YAML。

## 技术架构

```
src/
├── cli.py              # 统一 CLI 入口
├── config/
│   ├── schema.py       # Pydantic 数据模型
│   └── loader.py       # YAML 加载/校验/导入
├── engine/
│   ├── calendar.py     # AKShare 交易日历
│   ├── events.py       # 事件生成 (BUY/CALIBRATE)
│   └── calculator.py   # 事件驱动计算引擎 + XIRR + 校准
├── analysis/
│   ├── scorer.py       # 三因子评分
│   ├── holdings.py     # 持仓分析
│   ├── correlation.py  # 相关性矩阵
│   └── stress.py       # 情景压力测试
├── data/
│   └── fetcher.py      # AKShare 数据采集
├── news/
│   ├── news_fetcher.py # 新闻抓取
│   └── sentiment.py    # 情绪分析
├── recommend/
│   └── engine.py       # 基金推荐引擎
├── output/
│   └── report.py       # Markdown 报告生成
├── db/
│   ├── models.py       # SQLAlchemy ORM
│   ├── database.py     # 数据库连接
│   └── storage.py      # 高层存储 API
└── ui/
    └── app.py          # Streamlit 交互界面
```

## 分析流水线

`analyze` 使用只读持仓配置生成报告：

1. 加载并校验 `fund-portfolio.yaml`
2. 同步基金基础元数据到 SQLite
3. 按当前配置中的持仓基金采集 AKShare 数据
4. 以报告口径日计算持仓：交易日 21:30 前使用上一交易日
5. 事件驱动计算份额、pending、XIRR，并在有 `shares`/`avg_cost` 时优先使用真实持仓口径
6. 生成评分、新闻、推荐、压力测试和 Markdown 报告
7. 保存分析快照，用于后续评分趋势对比

`snapshot` 是独立的配置滚动步骤，只在你确认需要把已执行定投写回 YAML 时运行。

报告会按口径日计算数据，但输出不再区分交易日/非交易日模板，而是合并展示完整工作流：

- 交易相关跟踪：QDII 结算状态、定投执行/预计确认、简要市场环境和资产变化根因。
- 组合复盘：本周收益贡献、风险暴露/再平衡、定投质量分析。

## License

MIT
