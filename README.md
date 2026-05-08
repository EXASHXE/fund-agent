# Fund Agent

量化基金分析工具，核心输出基金诊断报告与投资建议。

## 功能

- **数据采集**：通过 AKShare 获取基金净值、业绩指标、持仓明细、新闻资讯
- **多因子评分**：宏观(20%) / 中观(30%) / 微观(50%) 三维度打分，输出操作建议
- **持仓分析**：事件驱动计算引擎、XIRR 年化收益、校准平账、QDII T+2 结算支持
- **组合诊断**：相关性矩阵、情景压力测试、行业集中度、再平衡方案
- **新闻情绪分析**：基金相关新闻抓取 + 中文情绪分析 + 新闻-净值相关性
- **基金推荐**：基于热点行业全市场筛选 + 与持仓相关性过滤
- **交互式 UI**：Streamlit Web 界面，持仓总览 / 基金详情 / 定投管理 / 增删基金

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化配置文件
python3 -m src.cli init -o fund-portfolio.yaml

# 编辑 fund-portfolio.yaml 填入你的持仓数据

# 运行完整分析
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# 或启动交互式界面
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

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

## 计算引擎

事件驱动流水线：事件生成 → 净值匹配 + PENDING 检查 → 校准平账，详见 `CLAUDE.md`。

## License

MIT
