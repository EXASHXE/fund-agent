# Fund Analysis Project

## 项目性质

量化基金分析工具，核心输出基金诊断报告与投资建议。

## 自动行为

- 遇到基金分析任务时，主动加载 `skills/fund-analyst/SKILL.md` 中的三层分析流程
- 所有分析输出使用**中文**
- 所有金额、百分比、指标保留**至少 2 位小数**（成本价 4 位除外）
- 数据源默认使用 AKShare；数据缺失时降级不中断
- 持仓配置使用 YAML 格式 (fund-portfolio.yaml)，通过 CLI 导入/分析

---

## fund-agent CLI 命令

```bash
# 初始化：生成示例 YAML（首次使用）
python3 -m src.cli init -o fund-portfolio.yaml

# 导入持仓到数据库（每次 YAML 变更后）
python3 -m src.cli import -c fund-portfolio.yaml

# 完整分析：导入 + 采集 + 评分 + 持仓分析 + 新闻 + 报告
# 推荐、压力测试默认关闭，可通过 --recommend --stress 启用
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# 完整分析含推荐 + 压力测试
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --recommend --stress

# 更新时间 仅快照 不分析

# 单基金快速诊断
python3 -m src.cli diagnose 008253

# 新闻分析（仅采集+情绪分析，不生成报告）
python3 -m src.cli news -c fund-portfolio.yaml --days 7

# 基金推荐（基于近期新闻热点+全市场筛选）
python3 -m src.cli recommend -c fund-portfolio.yaml --top 5

# 启动交互式管理界面（Streamlit Web UI，修改实时写入 YAML）
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501

# 仅拉取净值数据（不分析）
python3 -m src.cli fetch -c fund-portfolio.yaml

# 对数据库现有持仓评分（不重新导入）
python3 -m src.cli score -o report.md
```

## 标准分析流程

```
Layer 1: 数据采集 → Layer 2: 分析评分 → Layer 3: 新闻分析 → Layer 4: 报告生成
```

1. 检查 `fund-portfolio.yaml` 是否存在，不存在则引导用户创建
2. `python3 -m src.cli import -c fund-portfolio.yaml` — 导入持仓到数据库
3. `python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md` — 完整分析
4. 读取 `report.md` 展示结果
5. `python3 -m src.cli snapshot -c fund-portfolio.yaml` — 更新 DCA 日期

## 技术架构

```
src/
├── cli.py              # 统一 CLI 入口
├── config/
│   ├── schema.py       # Pydantic 数据模型（YAML ↔ 对象）
│   ├── loader.py       # YAML 加载/校验/导入
│   ├── defaults.py     # 全局默认参数
│   └── shared.py       # 共享工具函数
├── engine/
│   ├── calendar.py     # AKShare 交易日历
│   ├── events.py       # 事件生成（BUY / CALIBRATE）
│   └── calculator.py   # 核心计算引擎（事件驱动 + XIRR + 校准）
├── analysis/
│   ├── scorer.py       # 三因子评分（宏观/中观/微观）
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

## 计算引擎设计

### 事件驱动流水线

```
Stage 1: 事件生成 (events.py)
  YAML purchases → BUY events
  DCA 推演 → BUY events
  calibrations → CALIBRATE events
  按时间排序 → events_ledger

Stage 2: 净值匹配 + PENDING 检查 (calculator.py)
  净值匹配: resolve_nav_date(date, after_1500, settle_delay=1)
    - 非交易日 → 顺延至下一交易日
    - 交易日 + after_1500 → 顺延至下一交易日
  PENDING 检查: _settlement_date(purchase_date, settle_delay)
    - 国内 (settle_delay=1): T+1 交易日到账
    - QDII (settle_delay=2): T+2 交易日到账
    - 到账日 > 今天 → 标记 PENDING（不入计算）

Stage 3: 校准平账
  delta = actual_shares - total_shares
  delta_pct = |delta| / actual_shares
  ≤ 3% → 自动覆盖 total_shares
  > 3% → 拒绝并报警
  total_cost 永不修改
```

### 关键设计决策

- **净值匹配用 settle_delay=1**：AKShare 净值日期即为有效申购净值日，与结算到账时间无关
- **settle_delay 字段**：仅用于 PENDING 截止日计算（1=T+1 国内，2=T+2 QDII）
- **校准阈值 3%**：小于则自动校准平账，大于则拒绝要求人工排查
- **QDII 展示净值 1 天偏移**：AKShare 标注 QDII 净值为"计算日"，券商 App 显示"公布日(+1天)"，展示时用前一日净值
- **份额按交易日到账**：QDII 买入后 T+2 交易日才计入持仓（周五→下周二），国内 T+1
- **短期持有不显 XIRR**：持有 <365 天显示"短期不适用"
- **统一 PENDING 规则**：`settlement_date >= today` 所有类型基金统一排除当天结算份额
- **不做 NAV 指数外推**：QDII 净值滞后时不做指数估算，保证与券商口径一致

### 引擎验证状态

经 25 个交易日券商实盘数据逐日验证（4月21天 + 5月4天），日盈亏平均误差 ¥0.008，最大误差 ¥0.03。
当前报告与券商持仓完全对齐（<0.01% 误差）。

## YAML 新增字段

| 字段               | 类型    | 说明                           |
| ---------------- | ----- | ---------------------------- |
| `avg_cost`       | float | 持仓成本价                        |
| `shares`         | float | 当前持有份额                       |
| `pending_amount` | float | 待确认金额（在途申购）                  |
| `settle_delay`   | int   | 结算延迟：1=T+1(国内) / 2=T+2(QDII) |

## 交互式界面 (Streamlit)

启动: `python3 -m src.cli ui -c fund-portfolio.yaml -p 8501`

四个页面：

1. **持仓总览** — 市值/成本/待确认卡片 + 基金详情表
2. **基金详情** — 选中基金，编辑费率/成本价/份额/待确认金额，查看买入记录和校准记录。点击"保存修改"直接写回 YAML
3. **定投管理** — 启用/停用/修改频率/金额/定投日，保存后写入 YAML
4. **新增/删除** — 添加基金（自动查询名称），删除基金实时更新 YAML
