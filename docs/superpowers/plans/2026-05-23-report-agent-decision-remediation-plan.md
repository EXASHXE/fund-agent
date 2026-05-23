# Fund Agent 报告质量与 Agent 决策闭环修正实施计划

> 日期：2026-05-23  
> 用途：交给 AI Agent 直接执行的完整修正计划  
> 工作目录：`/root/workspace/project/fund-agent`  
> 目标产物：结构清晰、数据口径一致、由 Agent 给出最终研判的 `report.md`

## 0. 执行前必读

### 0.1 当前工作区约束

当前仓库存在大量未提交修改，覆盖 `src/cli.py`、`src/output/report.py`、`src/news/*`、`src/engine/*`、测试和 skill 文档。执行 Agent 必须：

1. 先运行 `git status --short --branch` 并阅读任务涉及文件的当前内容和 diff。
2. 将现有未提交修改视为用户成果，禁止使用 `git checkout --`、`git reset --hard` 或整体覆盖方式回退。
3. 修改前先补充或调整测试，用当前工作树作为唯一事实基线。
4. 每一阶段完成后运行该阶段测试；全部阶段完成后重新生成并人工审计 `report.md`。

### 0.2 本计划解决的明确问题

当前 `report.md` 已确认存在以下问题：

| 编号 | 问题 | 当前表现 |
|---|---|---|
| R1 | 新闻样本少且集中度过高 | `378006` 的精选新闻主要是腾讯连续回购，缺少其他重仓和市场区域覆盖 |
| R2 | 新闻折叠排版不稳定 | `<details>` 在展示环境中可能直接露出 `</details>`，展开后多条内容拥挤 |
| R3 | 情绪逻辑失真 | 新闻情绪主要出现 `0.35 / 0.50 / 0.65`，且最终报告仍提示未有 Agent 研判 |
| R4 | 跨报告日期污染 | 报告口径日为 `2026-05-22`，却将 `2026-05-23` 新闻列入当日归因 |
| R5 | QDII/T-1 识别误判 | `021620` 为国内指数、`settle_delay: 1`，却显示 `T-1估算净值` |
| R6 | 当日收益缺乏平台对账精度 | `008253` 报告为 `+633.82`，用户平台实值为 `+633.60` |
| R7 | 结算状态范围和顺序不正确 | 仅输出 `QDII 结算状态`，且位置在定投执行表之前 |
| R8 | 报告暴露规则动作结论 | 仍输出趋势预测与操作矩阵、操作触发条件、建议占比、调整金额和规则动作 |
| R9 | Agent 最终评分未进入报告 | 单基金表仍显示“规则初稿；尚未提供 agent 前置决策 JSON” |
| R10 | 单基金信息密度过高 | 每只基金完整展开，缺乏适合阅读的折叠摘要 |
| R11 | 章节编号断裂 | 当前从“四”直接跳到“六”“七”“八”，缺失“五” |
| R12 | 流水线去重疑似二次过滤 | 抓取阶段复用共享 `seen`，pipeline 随后再次用同一集合 exact dedup |

### 0.3 架构原则

本次修正不能只做排版补丁。最终系统必须遵循以下边界：

1. **代码负责可复核证据**：净值、份额、收益、结算、新闻采集/相关性/覆盖度、量化基准特征、风险约束。
2. **Agent 负责最终研判**：新闻判断、宏观/中观/微观最终评分、趋势判断、买卖/定投动作、目标配置和触发条件。
3. **规则引擎不得伪装成最终投资决策**：规则动作、规则目标占比和规则调整金额不得直接展示为最终报告结论。
4. **成品报告不得含待填提示**：最终 `report.md` 不得出现 `<!-- AGENT:`、`AGENT_FILL`、`尚未提供 agent`、`前置决策 JSON` 等内容。
5. **任何归因都受口径日限制**：报告中用于解释收益的新闻、净值和执行状态均不得晚于报告口径日，盘后信息只能放入观察区。

---

## 1. 目标报告形态

### 1.1 报告生成状态

将报告明确分为两个状态，禁止混淆：

| 状态 | 文件建议 | 用途 | 允许内容 |
|---|---|---|---|
| Evidence Draft | `report.evidence.md` 或 `report.md` 加显著草稿标识 | 代码生成后供 Agent 阅读 | 量化证据、Agent 输入上下文、待决策标识 |
| Final Report | `report.md` | 用户阅读的最终报告 | 已填充的 Agent 研判与最终结论，不含占位符 |

推荐实现：CLI 新增 `--agent-decisions <json>` 参数。未传参数时生成 evidence draft；传入 Agent 输出 JSON 后重新渲染 final report。

### 1.2 最终章节结构

删除当前规则生成的“趋势预测与操作矩阵”和“操作触发条件”章节。最终报告统一使用以下顺序，不得缺号：

| 章节 | 标题 | 决策归属 |
|---|---|---|
| 一 | 新闻资讯与 Agent 舆情研判 | 证据 + Agent |
| 二 | 持仓总览与收益口径 | 引擎证据 |
| 三 | 定投执行与申购结算状态 | 引擎证据 |
| 四 | 单基金深度诊断 | 证据 + Agent 最终评分 |
| 五 | 组合研判与执行方案 | Agent 最终动作/仓位/触发条件 |
| 六 | 组合风险、相关性与压力测试 | 证据 + Agent 风险解释 |
| 七 | 推荐候选与观察池 | Agent 最终筛选，可为空 |
| 附录 | 数据口径与风险提示 | 固定说明 |

### 1.3 禁止直接出现在最终报告中的字段

以下内容可在内部 evidence JSON 保存，但不得作为规则结论直接展示：

- `operation_advice.action`
- `operation_advice.target_weight`
- `operation_advice.adjust_amount`
- 规则生成的 `triggers`
- 规则生成的“建议动作”“建议占比”“调整金额”
- “规则初稿；尚未提供 agent 前置决策 JSON”
- “新闻情绪为规则初稿；尚未提供 agent 前置新闻研判”

若 Agent 最终判断使用了同名概念，应来自 `agent_decisions`，并标记为 Agent 结论。

---

## 2. 建议的数据契约

### 2.1 引擎输出 evidence 数据结构

新增或稳定化一个可序列化的证据对象，例如 `report.evidence.json`。最少包括：

```json
{
  "schema_version": "report_evidence.v2",
  "report_date": "2026-05-22",
  "generated_at": "2026-05-23T00:00:00+08:00",
  "report_status": "awaiting_agent_decisions",
  "portfolio": {
    "total_value": 0,
    "total_cost": 0,
    "total_profit": 0,
    "daily_profit": 0,
    "daily_return_pct": 0
  },
  "funds": {
    "008253": {
      "identity": {},
      "holding_metrics": {},
      "settlement": {},
      "profit_reconciliation": {},
      "quant_baseline": {},
      "factor_matrix": {},
      "news_evidence": {},
      "risk_constraints": {}
    }
  },
  "portfolio_evidence": {
    "correlations": {},
    "stress_tests": [],
    "cluster_exposures": {}
  }
}
```

要求：

- `report_date` 是所有报告数据筛选的上界。
- `quant_baseline` 只表示规则/量化证据，不能附带最终推荐。
- `risk_constraints` 可以包含单仓上限、相关性预警、pending 风险等硬约束，但不能输出自动交易动作。
- evidence 应保留新闻覆盖质量、份额对账和净值来源，便于 Agent 不凭空推断。

### 2.2 Agent 决策输入结构

Agent 阅读 evidence 后产出 `agent_decisions.json`，建议契约如下：

```json
{
  "schema_version": "agent_decisions.v2",
  "evidence_report_date": "2026-05-22",
  "portfolio": {
    "stance": "neutral",
    "tldr": "组合最终结论",
    "key_risks": ["风险一"],
    "allocation_rationale": "资金安排逻辑",
    "cash_or_pending_note": "结算与待确认影响"
  },
  "news": {
    "008253": {
      "impact": "positive",
      "relevance": "medium",
      "confidence": 0.72,
      "summary": "基于可验证新闻的研判",
      "coverage_limitation": "样本覆盖不足说明",
      "watch_items": ["观察项"]
    }
  },
  "fund_scores": {
    "008253": {
      "rule_scores": {"macro": 0, "meso": 0, "micro": 0, "total": 0},
      "agent_adjustments": {"macro": 0, "meso": 0, "micro": 0},
      "final_scores": {"macro": 0, "meso": 0, "micro": 0, "total": 0},
      "confidence": 0.0,
      "rationale": ["证据及修正理由"],
      "trend_view": {"short_term": "", "mid_term": "", "reason": ""},
      "final_action": "hold",
      "target_weight_pct": null,
      "adjust_amount": null,
      "triggers": ["Agent 制定的可执行条件"]
    }
  },
  "recommendations": []
}
```

约束：

1. `rule_scores` 必须与 evidence 一致，不得由 Agent 改写。
2. `agent_adjustments` 必须有理由、置信度和风险触发条件。
3. `final_action`、`target_weight_pct`、`adjust_amount` 只来自 Agent 决策，不得从旧的规则输出自动回填。
4. Agent 不确定或样本不足时，可使用 `observe` / `insufficient_evidence`，不得强行给买入结论。

### 2.3 最终报告渲染规则

报告生成器只在 `agent_decisions.evidence_report_date == evidence.report_date` 时生成 final report。否则：

- 拒绝将旧 Agent 结论套用到新证据；
- 输出明确错误，或继续保留 evidence draft；
- 不得悄悄展示规则结论代替 Agent 决策。

---

## 3. 分阶段实施计划

## Phase 0：保护基线与增加验收夹具

### 目标

在修改行为前，固定当前错误案例与目标结果，防止修正过程中回退或误解需求。

### 涉及文件

- `tests/test_report_agent_decisions.py`
- `tests/test_workflow_context.py`
- `tests/test_news_fetcher.py`
- `tests/test_news_evaluator.py`
- `tests/test_engine_calculator.py`
- 可新增：`tests/test_report_rendering_contract.py`
- 可新增：`tests/fixtures/report_goal_cases.json`

### 任务

1. 建立报告输出契约测试：
   - 最终报告不存在“趋势预测与操作矩阵”；
   - 最终报告不存在“操作触发条件”规则章节；
   - 最终报告不存在规则生成的“建议占比”“调整金额”“建议动作”表头；
   - 最终报告章节编号连续，至少包括“一”至“七”；
   - 最终报告不存在待 Agent 提示文本和 HTML 裸闭合标签显示问题。
2. 建立已知样本测试：
   - `021620` 配置为 `type=index, settle_delay=1` 时不出现 T-1 标签；
   - `008253` 的指定平台确认份额/净值样本应得到 `+633.60` 或明确对账差异；
   - 口径日 `2026-05-22` 时，`2026-05-23` 新闻不能进入当日新闻或当日归因。
3. 建立 pipeline 回归测试：
   - 单基金采集一条新闻后，经过 pipeline 仍保留该新闻；
   - 跨基金共享新闻可以在全局聚类中复用，但不得使本基金结果空掉；
   - 事件聚合后腾讯连续回购可显示为一类事件及多次发生，而不是虚增独立主题覆盖。
4. 更新旧测试：
   - 删除或改写当前断言“趋势预测与操作矩阵必须渲染”“操作触发条件必须渲染”的测试；
   - 新断言应检查 Agent 决策章节渲染，而不是规则章节渲染。

### 完成标准

新增测试先在旧实现上准确失败，失败原因对应 R4/R5/R7/R8/R9/R11/R12；实现修正后全部转绿。

---

## Phase 1：报告日期、净值标记和结算口径修正

### 目标

优先修复会直接导致用户误读的事实错误。

### 涉及文件

- `src/output/templates.py`
- `src/cli.py`
- `src/output/report.py`
- `src/config/schema.py`（仅在需要补类型/状态字段时修改）
- `tests/test_workflow_context.py`
- `tests/test_report_agent_decisions.py`
- `tests/test_engine_calculator.py`

### 1.1 修正 T-1/QDII 判断

当前错误根因：`is_qdii_fund()` 依据名称含 `"石油"` 推断海外基金，导致国内 `021620` 被误标。

实现要求：

1. 移除主题关键词推断 QDII 的逻辑。
2. `T-1` 提示使用结构化事实判断：
   - 首选 `fund_type == "qdii"`；
   - 或使用明确的 `nav_lag_status` / `nav_date < report_date`；
   - `settle_delay` 只代表申购确认延迟，不应独自推导净值一定为估算。
3. 标签文案应区分：
   - `净值日期滞后：YYYY-MM-DD`；
   - `申购确认中`；
   - `估算净值` 仅在确实调用估值逻辑时出现。

验收：

```text
021620 天弘石油天然气指数C
```

不得带 `T-1估算净值`；QDII 若实际最新净值已是报告口径日，也不得机械带估算标签。

### 1.2 统一结算状态并调整位置

当前错误根因：`_build_workflow_context()` 仅构建 `qdii_rows`，渲染器固定标题为 `QDII 结算状态`。

实现要求：

1. 将 `qdii_rows` 更名/替换为 `settlement_rows`，包含所有持仓基金。
2. 每只基金至少输出：
   - 基金代码与名称；
   - 产品类型；
   - 最新净值日期；
   - 净值口径状态；
   - 已确认份额；
   - 待确认金额；
   - 下一确认日；
   - 结算状态。
3. 在报告第三章节中排序为：
   - `定投执行与确认预估`
   - `申购与净值结算状态`
   - `待确认事件明细`（存在时）
4. QDII 仅在状态列或风险列标注“海外净值披露延迟风险”，不作为独立表分类。

### 1.3 强制报告口径日上界

实现要求：

1. 将 `report_date` 显式传入新闻 pipeline、新闻评估和工作流构建方法。
2. 新闻采集可保留更新数据供观察，但必须分成：
   - `as_of_news`: `date <= report_date`，允许进入收益归因；
   - `post_cutoff_news`: `date > report_date`，只允许进入“盘后观察”。
3. 无日期新闻不得进入“当日归因”；可列入“日期缺失样本，未纳入归因”。
4. 所有总数和情绪/催化聚合必须说明计算使用的是 `as_of_news` 还是全量观察新闻。

验收：

- 报告日期为 `2026-05-22` 时，当日新闻线索表没有 `2026-05-23` 项；
- 如保留 `2026-05-23` 新闻，必须位于清晰标注的“口径日后观察”区域。

---

## Phase 2：收益精度与对账证据修正

### 目标

将收益误差从“猜测四舍五入”转化为可定位、可回归的对账过程。

### 涉及文件

- `src/engine/calculator.py`
- `src/engine/events.py`
- `src/cli.py`
- `src/analysis/holdings.py`
- `src/output/report.py`
- `fund-portfolio.yaml`（只在用户确认真实平台数据后更新校准点）
- `tests/test_engine_calculator.py`

### 2.1 定义当日收益口径

报告中必须区分以下金额：

| 字段 | 定义 |
|---|---|
| `confirmed_daily_profit` | 仅已确认份额按两个净值日差额计算的日收益 |
| `pending_amount` | 已扣款但尚未确认份额的资金 |
| `platform_daily_profit` | 用户平台提供的当日收益，可为空 |
| `reconciliation_delta` | 引擎值减平台值 |
| `reconciliation_status` | `matched` / `within_tolerance` / `needs_calibration` / `no_platform_reference` |

### 2.2 处理 008253 样本

针对 `008253` 当前 `+633.82` 与平台 `+633.60` 的差异：

1. 检查计算所用份额是否为报告日真实已确认份额，而不是流水模拟份额或含待确认申购的份额。
2. 检查最新和前一净值是否保留足够原始精度，避免先四舍五入再相乘。
3. 检查校准事件发生后的份额是否在当日收益段正确应用。
4. 若平台收益包含其特殊计费或估值口径无法从公开净值复现，则：
   - 不伪造一致；
   - 显示引擎估算、平台参考和差额原因；
   - 将平台确认份额/收益作为可选输入证据。

### 2.3 报告展示

持仓总览可保持精简，但第三章节增加“收益口径与对账状态”：

```markdown
| 基金 | 引擎当日收益 | 平台参考 | 差额 | 对账状态 | 计算依据 |
|------|-------------:|---------:|-----:|----------|----------|
| 008253 | +633.60 | +633.60 | 0.00 | 已对齐 | 已确认份额 × NAV 差额 |
```

不存在平台参考时应显示 `未录入平台参考`，不得声称“精确一致”。

### 完成标准

- 008253 有固定测试夹具，并能证明差异已解决或可解释；
- 计算过程全程使用高精度数值，只在展示阶段格式化到两位金额；
- 当日收益不得计入尚未确认份额带来的虚假波动。

---

## Phase 3：新闻采集覆盖、去重和评分逻辑修正

### 目标

新闻模块从“少量泛匹配 + 离散情绪档位”升级为“持仓覆盖可见 + 事件质量可评估 + Agent 可据此判断”。

### 涉及文件

- `src/news/news_fetcher.py`
- `src/news/pipeline.py`
- `src/news/deduplicator.py`
- `src/news/entity_mapper.py`
- `src/news/catalyst.py`
- `src/news/evaluator.py`
- `src/news/sentiment.py`
- `src/news/agent_context.py`
- `src/output/report.py`
- `tests/test_news_fetcher.py`
- `tests/test_news_evaluator.py`
- 可新增：`tests/test_news_pipeline.py`

### 3.1 新闻覆盖模型

每只基金不能只输出“新闻数”。需增加以下覆盖指标：

| 指标 | 含义 |
|---|---|
| `holding_coverage_count` | 前十大持仓中至少有一条相关信息的持仓数量 |
| `holding_coverage_pct` | 按持仓权重计算的新闻覆盖比例 |
| `sector_coverage` | 行业/主题覆盖列表 |
| `region_coverage` | 国内、港股、美国、其他新兴市场等覆盖 |
| `independent_event_count` | 事件归并后的独立事件数 |
| `source_count` | 独立来源数 |
| `repetition_ratio` | 重复/同类事件占比 |
| `coverage_warning` | 覆盖过窄时的明确提示 |

针对 `378006`：

- 腾讯连续回购应归并为一个“腾讯回购持续发生”事件，并保留发生次数；
- 若未覆盖台积电、三星、阿里、其他地区/行业重仓，报告必须显示“覆盖偏窄，不能代表全球新兴市场整体新闻面”；
- 不得因为同一公司同类新闻多次出现而输出“全场最佳”“置信度高”之类结论，除非 Agent 在覆盖限制下明确论证。

### 3.2 数据源和搜索策略

执行 Agent 应先验证 AKShare 当前可用数据源，再按以下优先级组织数据：

1. 基金披露的前十大持仓公司新闻；
2. 基金主题/行业新闻；
3. 基金覆盖区域或基准市场新闻；
4. 宏观事件，只在传导关系可说明时纳入。

实现规则：

- 每个基金使用持仓画像生成公司级搜索词和行业/区域级搜索词；
- 对海外持仓同时保留英文代码、英文公司名与中文通用名；
- 限制过宽关键词如单独 `"AI"`、`"能源"` 带来的泛新闻污染；
- 对每条新闻保存命中层级：`holding` / `sector` / `region` / `macro_proxy`。

### 3.3 修复去重链路

当前风险：`fetch_fund_news(... shared_seen=global_seen)` 已将新闻写入共享集合，`run_news_pipeline()` 又调用 `exact_dedup(news_list, global_seen)`。

推荐方案：

1. 抓取函数只负责基金内标题去重，不使用跨基金集合丢弃新闻；
2. pipeline 先形成每基金完整证据，再单独维护 portfolio-level event map 用于说明事件影响多只基金；
3. 同一事件影响多个基金时，每个基金都保留该证据，并标注共享事件 ID；
4. 仅在组合汇总显示时合并重复描述，不能在单基金 evidence 中消失。

### 3.4 重构新闻评分

当前 `0.35 / 0.50 / 0.65` 的根因是固定影响权重配合正负词映射。修正后：

1. 不再把 `sentiment_mean` 作为主结论，重命名为 `lexicon_signal` 或移入附加指标。
2. 主新闻量化证据应至少包括：
   - `catalyst_score`：方向与事件影响；
   - `relevance_score`：对真实持仓的相关性；
   - `quality_score`：来源、日期、样本量和覆盖；
   - `decayed_score`：截至报告日的时间衰减结果；
   - `confidence_cap`：覆盖不足时的置信度上限。
3. `analyze_sentiment()` 如继续使用，必须传入真实持仓/主题关键词；否则 impact 不得被展示为基金相关影响。
4. `daily_sentiment_aggregate()` 的时间衰减终值应实际接入报告和 Agent context，不能计算后丢弃。
5. Agent 最终舆情研判单独展示，不与词典信号混为一列。

### 3.5 新闻展示组件

每只基金新闻显示为折叠卡片，摘要可见：

```markdown
<details>
<summary>378006 摩根全球新兴市场 | 独立事件 2 | 覆盖偏窄 | Agent: 中性偏正</summary>

| 指标 | 值 |
|---|---:|
| 独立事件数 | 2 |
| 持仓覆盖 | 2/10 |
| 覆盖警告 | 新闻集中在腾讯/阿里，不能代表全部新兴市场敞口 |

**Agent 研判：** ...

**事件明细**

| 日期 | 关联持仓 | 事件 | 方向 | 相关性 | 来源 |
|---|---|---|---|---:|---|
| 2026-05-22 | 腾讯 | 连续回购事件（第 5 日） | 正面 | 0.85 | ... |

</details>
```

渲染要求：

- `<summary>` 和内部 Markdown 之间保留空行；
- 每个 `<details>` 必须在同一生成函数路径中闭合；
- 不将多条新闻塞入一个无换行文本行；
- 增加字符串契约测试，检查 `<details>` 开闭数量相同。

---

## Phase 4：拆除规则投资结论并接入 Agent 最终决策

### 目标

结构化引擎只生成分析证据和硬风险约束，最终预测、动作、资金分配及评分由 Agent 负责。

### 涉及文件

- `src/cli.py`
- `src/output/report.py`
- `src/analysis/scorer.py`
- `src/forecast/engine.py`
- `src/decision/engine.py`
- `src/news/agent_context.py`
- `src/db/models.py`
- `src/db/storage.py`
- `tests/test_agent_context.py`
- `tests/test_forecast_decision.py`
- `tests/test_report_agent_decisions.py`
- `tests/test_snapshot_sanitize.py`

### 4.1 规则评分与 Agent 评分分层

规则层允许输出：

- 宏观、中观、微观量化基准分；
- factor matrix、feature matrix；
- 数据完整度、评分置信度；
- 风险边界和数据缺口。

规则层不得以最终报告口吻输出：

- 买入、卖出、加仓、减仓建议；
- 目标配置占比；
- 调整金额；
- 可被误解为已批准交易的触发动作。

### 4.2 重构 `operation_advice` 和趋势模块

建议处理方式：

1. `forecast.engine` 保留中性证据特征，例如动量分、催化分、波动/回撤信号，可命名为 `trend_evidence`。
2. `decision.engine.build_operation_advice()` 不再由正常报告流程调用；若暂时为兼容历史快照保留，应标为 deprecated/internal。
3. `_attach_trends_and_advice()` 改为 `_attach_decision_evidence()`：
   - 生成风险约束；
   - 生成趋势信号证据；
   - 不生成动作、目标占比和调整金额。
4. 旧 snapshot 如需要保留字段，应在 schema 版本中明确为历史字段，不能用于新报告回填。

### 4.3 Agent 决策接入 CLI

建议 CLI 流程：

```text
analyze without --agent-decisions
  -> 采集/计算/生成 report.evidence.json 和 report.evidence.md
  -> 提示需由 Agent 生成 agent_decisions.json

analyze --agent-decisions agent_decisions.json
  -> 验证 schema 和 evidence_report_date
  -> 生成最终 report.md
  -> 运行最终报告校验
```

可选增强：

- `render-final --evidence report.evidence.json --agent-decisions agent_decisions.json -o report.md`
- 这样可避免为了渲染最终报告再次联网采集数据导致口径漂移。

### 4.4 单基金诊断最终表

每只基金使用统一折叠块，摘要显示最终结论：

```markdown
<details>
<summary>008253 华宝致远混合(QDII)A | Agent 最终分 62/100 | 动作：继续观察 | 风险：海外科技集中</summary>

| 维度 | 量化基准分 | Agent 调整 | 最终分 | 调整依据 |
|---|---:|---:|---:|---|
| 宏观 | 12/20 | +1 | 13/20 | ... |
| 中观 | 18/30 | -2 | 16/30 | ... |
| 微观 | 28/50 | 0 | 28/50 | ... |
| 综合 | 58/100 | -1 | 57/100 | ... |

**Agent 趋势判断：** ...

**Agent 最终动作与触发条件：** ...

</details>
```

注意：

- “规则初稿；尚未提供 agent 前置决策 JSON”必须完全移除；
- Evidence Draft 中可显示“待 Agent 评定”，但 Final Report 绝不允许存在；
- Agent 最终分必须来源于决策 JSON，而不是 Python 私自模拟 AI 调整。

### 4.5 组合执行方案章节

在最终报告第五章节展示 Agent 结果：

```markdown
## 五、组合研判与执行方案

| 基金 | 当前占比 | Agent 最终动作 | Agent 目标范围 | 本期调整金额 | 触发条件 |
|---|---:|---|---:|---:|---|
```

该章节可包含目标占比和调整金额，但前提是数据来源为 `agent_decisions`。标题和正文必须写明是“Agent 最终建议”，避免与规则引擎结论混淆。

---

## Phase 5：报告渲染、章节与最终校验

### 目标

使 `report.md` 在内容和展示上均达到可交付状态。

### 涉及文件

- `src/output/report.py`
- `src/output/templates.py`
- `src/output/validator.py`
- `tests/test_report_agent_decisions.py`
- 可新增：`tests/test_report_rendering_contract.py`

### 5.1 章节重排

渲染器按第 1.2 节结构固定章节，不再让可选模块造成编号断裂。可选内容为空时保留标题并写明“本期无符合条件项目”。

### 5.2 折叠组件统一

新增内部渲染 helper，例如：

```python
def _render_details(summary: str, body_lines: list[str]) -> list[str]:
    return [
        "<details>",
        f"<summary>{summary}</summary>",
        "",
        *body_lines,
        "",
        "</details>",
        "",
    ]
```

所有新闻和单基金折叠内容统一使用该 helper，避免闭合遗漏、格式漂移和裸标签。

### 5.3 Final Report validator

扩展后置校验，使最终报告在写出前失败阻断：

| 校验 | 失败条件 |
|---|---|
| Agent 完成度 | 存在 `AGENT_FILL`、`<!-- AGENT:`、`尚未提供 agent` |
| 章节连续性 | 缺少一至七任一章节，或存在废弃规则章节 |
| 规则输出泄漏 | 存在规则版“趋势预测与操作矩阵”/“操作触发条件” |
| HTML 完整性 | `<details>` 与 `</details>` 数量不等 |
| 日期一致性 | 收益归因区域出现晚于报告日的新闻日期 |
| 状态范围 | 结算状态表未覆盖全部持仓基金 |
| 标签正确性 | 非 QDII/非滞后净值基金被标记 T-1 估算 |

Validator 失败应抛出明确异常或生成失败状态，不应安静输出不完整报告。

---

## Phase 6：文档与 Agent Skill 同步

### 目标

避免代码修正后，Skill 又要求 Agent 服从已废弃的规则动作。

### 涉及文件

- `README.md`
- `skills/fund-analyst/SKILL.md`
- `skills/fund-analyst/checklist.md`
- `skills/fund-analyst/calibration.md`
- `skills/fund-analyst/examples.md`
- `skills/fund-analyst/akshare-ref.md`

### 必须修改的契约表述

删除或重写如下旧表述：

- Agent 必须服从 `operation_advice.target_weight`；
- 调整金额不得由 Agent 修改；
- 趋势矩阵给定最终方向、Agent 只负责解释；
- 报告直接输出规则建议。

替换为：

1. Agent 必须尊重引擎证据和硬风险约束，但最终动作必须由 Agent 明确给出。
2. Agent 调整评分或配置时必须写明证据、风险、置信度和触发条件。
3. Evidence Draft 不能作为最终投资报告提交。
4. Final Report 必须由经过日期匹配的 `agent_decisions` 渲染生成。

### Skill 验收清单应包含

- [ ] Agent 使用的 evidence 与报告日期一致。
- [ ] 未将口径日后的新闻用于已发生收益归因。
- [ ] 每只基金均有量化基准分、Agent 调整和最终分。
- [ ] 最终操作、资金分配和触发条件明确标记为 Agent 结论。
- [ ] 新闻覆盖不足时降低结论置信度，没有因重复同类事件过度乐观。
- [ ] Final Report 无占位符、无废弃规则章节、章节编号连续。

---

## 4. 文件级变更清单

| 文件 | 主要变更 | 优先级 |
|---|---|---:|
| `src/news/pipeline.py` | 接受 `report_date`；切分口径内/口径后新闻；修复共享去重；输出覆盖与评价 | P0 |
| `src/news/news_fetcher.py` | 持仓/行业/区域分层采集；跨基金不丢证据；命中层级元数据 | P1 |
| `src/news/deduplicator.py` | 事件 ID 和重复事件聚类；连续回购等保留次数但不虚增主题 | P1 |
| `src/news/evaluator.py` | 覆盖度、来源多样性、质量、衰减催化和置信度上限 | P0 |
| `src/news/sentiment.py` | 降级为辅助信号；接入持仓词；暴露真实衰减终值 | P1 |
| `src/news/agent_context.py` | 输出完整 Agent 舆情/评分证据上下文 | P0 |
| `src/output/templates.py` | 删除主题名推断 QDII；净值滞后标签基于结构化状态 | P0 |
| `src/cli.py` | evidence/agent-decisions 两阶段；全基金结算；收益对账；不生成规则动作 | P0 |
| `src/engine/calculator.py` | 保留高精度日收益计算和对账字段 | P0 |
| `src/analysis/scorer.py` | 输出纯量化基准和风险证据，不输出最终投资结论 | P0 |
| `src/forecast/engine.py` | 从最终预测改为供 Agent 使用的趋势证据 | P1 |
| `src/decision/engine.py` | 移出新报告主流程，必要时保留历史兼容 | P1 |
| `src/output/report.py` | 新章节、Agent 最终表、统一折叠、移除规则表 | P0 |
| `src/output/validator.py` | Final Report 阻断式契约检查 | P0 |
| `src/db/storage.py` / `src/db/models.py` | 如保存 evidence/Agent 决策，增加 schema version 和来源标识 | P2 |
| `README.md` / `skills/fund-analyst/*` | 同步最终决策归属和执行流程 | P0 |
| `tests/*` | 覆盖本计划所有显式验收要求 | P0 |

---

## 5. 测试计划

### 5.1 单元测试

| 测试区域 | 必测场景 |
|---|---|
| QDII 标签 | 国内油气指数不显示 T-1；实际净值未滞后的 QDII 不显示“估算” |
| 日期截断 | 口径日后新闻不进入当日聚合和收益归因 |
| 情绪/催化 | 评分不再固定落在三档；覆盖不足压低置信度 |
| 新闻去重 | 单基金证据不被共享去重误删；同类事件聚类保留发生次数 |
| 结算状态 | 全部持仓基金均展示状态；表顺序在定投之后 |
| 日收益 | 使用真实确认份额与原始 NAV 精度；008253 样本可回归 |
| Agent schema | 日期不匹配时拒绝 final render；缺字段时报错 |
| 折叠渲染 | `<details>` 数量平衡；每基金有折叠块；新闻行分隔可读 |
| 最终报告 | 无占位、无旧规则章节、章节连续 |

### 5.2 集成测试

新增一条基于固定 fixture 的 end-to-end 流程：

1. 输入固定持仓、固定净值、固定新闻数据。
2. 生成 `report.evidence.json`。
3. 输入固定 `agent_decisions.json`。
4. 生成 `report.md`。
5. 断言：
   - `021620` 标签正确；
   - 008253 收益口径符合 fixture；
   - 378006 显示覆盖不足；
   - 最终章节连续；
   - 规则动作表不存在；
   - Agent 最终分和动作可见；
   - 无晚于报告日的归因新闻；
   - 无未填占位符。

### 5.3 实际报告回归

实现完成后，以当前真实配置执行：

```bash
PYTHONPATH=. pytest -q
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.evidence.md --no-snapshot-after
# 由 Agent 根据 evidence 生成 agent_decisions.json
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --agent-decisions agent_decisions.json --no-snapshot-after
```

若项目最终采用 `render-final` 子命令，应使用该命令替代第二次采集，优先避免数据漂移。

---

## 6. 最终验收清单

### 6.1 新闻模块

- [ ] 每只基金显示独立事件数、来源数、持仓/行业覆盖和覆盖警告。
- [ ] `378006` 不再仅凭腾讯重复回购新闻判定整体高置信利好。
- [ ] 报告口径日后的新闻未进入当日收益归因。
- [ ] 主信号使用催化、相关性、覆盖质量和 Agent 结论；旧词典情绪不再冒充最终判断。
- [ ] 新闻折叠卡片展开后行列清晰，页面不露出原始 `</details>`。

### 6.2 持仓与结算模块

- [ ] `021620` 不显示错误的 T-1/估算净值标记。
- [ ] `008253` 当日收益差异有测试证明已对齐或有可审计解释。
- [ ] 结算状态覆盖全部基金，不再只显示 QDII。
- [ ] “定投执行与确认预估”出现在“申购与净值结算状态”之前。

### 6.3 决策与单基金诊断

- [ ] 最终报告不显示规则生成的趋势/动作/目标占比/调整金额章节。
- [ ] 每只基金显示量化基准分、Agent 调整、最终分和依据。
- [ ] 每只基金深度诊断可折叠，摘要保留最终分、动作和首要风险。
- [ ] 组合执行方案中的动作、目标配置和金额仅来自 Agent 决策 JSON。

### 6.4 报告结构与文档

- [ ] 最终报告章节为一至七，编号连续，不存在缺失第五章节。
- [ ] Final Report 不存在任何 Agent 占位符或“尚未提供”提示。
- [ ] README 与 `skills/fund-analyst/*` 已同步“引擎给证据、Agent 给最终决策”的边界。
- [ ] `PYTHONPATH=. pytest -q` 全部通过。
- [ ] 使用当前 `fund-portfolio.yaml` 生成的新 `report.md` 经人工逐项复核通过。

---

## 7. 提交与执行顺序建议

为了降低同时改动造成的回归风险，建议 AI Agent 以以下原子步骤实施，每步完成后展示 diff 与测试结果：

1. **契约测试提交**：新增失败测试，固定错误样本与最终报告目标。
2. **事实口径提交**：修正口径日期、T-1 标签、全基金结算状态及展示顺序。
3. **收益对账提交**：补 008253 精度夹具、原始数值计算及对账展示。
4. **新闻质量提交**：修复去重、覆盖模型、事件聚类和主评分信号。
5. **Agent 决策协议提交**：加入 evidence / agent_decisions schema 与 final render。
6. **报告结构提交**：移除旧规则章节，加入单基金折叠和第五章 Agent 执行方案。
7. **文档同步提交**：更新 README 和 skill 契约。
8. **最终产物提交**：重新生成最终 `report.md`，附验收结果。

每个提交不得夹带与本计划无关的重构或格式化噪声。

---

## 8. 可直接发送给执行 Agent 的指令

```text
请依据 docs/superpowers/plans/2026-05-23-report-agent-decision-remediation-plan.md
完整实施修正，不要只做排版补丁。

执行要求：
1. 当前工作区已有未提交修改，先审阅 git status/diff，保留并基于现状增量修改，不得回退用户变更。
2. 先添加或调整能够暴露现有错误的测试，再实现代码修正。
3. 按 Phase 0 至 Phase 6 顺序推进；遇到实现细节差异可调整文件组织，但不得缩减验收范围。
4. 引擎只输出可复核证据和硬风险约束；Agent 输出最终评分、趋势、动作、资金配置和触发条件。
5. 最终 report.md 必须满足本计划第 6 节全部验收项，并附上测试结果与逐项验收证据。
```

