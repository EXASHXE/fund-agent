# Fund Analysis Project

## 项目性质

量化基金分析工具，核心输出基金诊断报告与投资建议。

## 自动行为

- 遇到基金分析任务时，主动加载 `skills/fund-analyst/SKILL.md` 中的三层分析流程
- 所有分析输出使用**中文**
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
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# 仅分析（跳过新闻/推荐，加快速度）
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-news --skip-recommend

# 导出持仓快照：更新 YAML 中 DCA 的 start_date 到下一个定投日（原地覆盖，自动备份 .bak）
python3 -m src.cli snapshot -c fund-portfolio.yaml

# 单基金快速诊断
python3 -m src.cli diagnose 008253

# 新闻分析（仅采集+情绪分析，不生成报告）
python3 -m src.cli news -c fund-portfolio.yaml --days 7

# 基金推荐（基于近期新闻热点+全市场筛选）
python3 -m src.cli recommend -c fund-portfolio.yaml --top 5

# 启动交互式管理界面（Streamlit Web UI，修改实时写入 YAML）
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

## 标准分析流程

1. 检查 `fund-portfolio.yaml` 是否存在，不存在则引导用户创建
2. `python3 -m src.cli import -c fund-portfolio.yaml` — 导入持仓到数据库
3. `python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md` — 完整分析
4. 读取 `report.md` 展示结果
5. `python3 -m src.cli snapshot -c fund-portfolio.yaml` — 更新 DCA 日期

## 技术架构

```
src/
├── cli.py              # CLI 入口
├── config/
│   ├── schema.py       # Pydantic 数据模型（YAML ↔ 对象）
│   └── loader.py       # YAML 加载/导入
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

## YAML 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `avg_cost` | float | 持仓成本价 |
| `shares` | float | 当前持有份额 |
| `pending_amount` | float | 待确认金额（在途申购） |
| `settle_delay` | int | 结算延迟：1=T+1(国内) / 2=T+2(QDII) |

## 交互式界面 (Streamlit)

启动: `python3 -m src.cli ui -c fund-portfolio.yaml -p 8501`

四个页面：
1. **持仓总览** — 市值/成本/待确认卡片 + 基金详情表
2. **基金详情** — 选中基金，编辑费率/成本价/份额/待确认金额，查看买入记录和校准记录。点击"保存修改"直接写回 YAML
3. **定投管理** — 启用/停用/修改频率/金额/定投日，保存后写入 YAML
4. **新增/删除** — 添加基金（自动查询名称），删除基金实时更新 YAML

---

# Superpowers-ZH 中文增强版

> 以下内容由 superpowers-zh 框架管理，与 fund-agent 业务逻辑独立。

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录。

- **brainstorming**: 在实现之前先探索用户意图、需求和设计
- **chinese-code-review**: 中文代码审查规范
- **chinese-commit-conventions**: 中文 Git 提交规范
- **chinese-documentation**: 中文技术文档写作规范
- **chinese-git-workflow**: 适配国内 Git 平台的工作流规范
- **dispatching-parallel-agents**: 2 个以上独立任务并行分发
- **executing-plans**: 执行已有书面实现计划
- **finishing-a-development-branch**: 开发分支收尾（合并/PR/清理）
- **mcp-builder**: MCP 服务器构建方法论
- **receiving-code-review**: 收到代码审查反馈后处理
- **requesting-code-review**: 完成任务后请求审查
- **subagent-driven-development**: 包含独立任务的实现计划执行
- **systematic-debugging**: 遇到 bug 时系统性调试
- **test-driven-development**: TDD 驱动开发
- **using-git-worktrees**: 隔离 git 工作树
- **using-superpowers**: 确立技能查找和使用方式
- **verification-before-completion**: 完成前必须验证
- **workflow-runner**: 直接运行 agency-orchestrator YAML 工作流
- **writing-plans**: 多步骤任务编写实现计划
- **writing-skills**: 创建/编辑/验证技能

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
