# Fund Agent 评分体系与趋势预测优化方案

> 分析日期：2026-05-21  
> 范围：当前 `fund-agent` 项目的数据采集、评分、新闻、趋势预测、推荐、持仓、报告输出与测试模块。  
> 目标：把现有“规则初评分 + Agent 报告填充”升级为“可解释量化评分 + 未来趋势评估 + 可执行操作建议”的闭环输出。

## 1. 当前项目画像

项目主线已经形成：`src/cli.py` 负责完整工作流编排，`src/analysis/scorer.py` 生成规则初评分和 `feature_matrix`，`src/news/` 生成新闻情绪与催化证据，`src/recommend/engine.py` 生成推荐候选，`src/output/report.py` 输出 Markdown 模板，再由 `skills/fund-analyst/SKILL.md` 约束 Agent 填充最终投研文本。

当前架构的优点：

- 已有三层评分契约：`quant_baseline`、`agent_overlay`、`final_score`。
- 已有核心风险收益特征：Sortino、HHI、Jensen Alpha、IR、Beta、最大回撤、年化波动率、Sharpe。
- 新闻模块已从简单情绪扩展到事件催化：`severity * impact * relevance * decay`。
- 持仓模块已覆盖真实流水、XIRR、QDII T+2、pending、定投滚动和校准提示。
- 推荐模块已有动量、热点、分散度、相似度、多样性约束。

当前主要短板：

- 评分基准仍大量依赖基金名称、类型和固定阈值，宏观/中观分缺少可观测市场变量。
- `feature_matrix` 生成后没有进入统一评分函数，部分高阶指标只展示，不真正改变基准分。
- “未来趋势预测”没有独立数据结构，新闻催化、净值动量、评分趋势、相关性、持仓成本分散在各模块。
- 操作建议仍以分数阈值映射为主，缺少“趋势方向 + 置信度 + 仓位约束 + 触发条件”的统一决策层。
- 报告输出仍保留大量占位符，Agent 可以补强文本，但缺少机器可校验的操作建议 JSON。

## 2. 模块级问题与优化方向

### 2.1 CLI 工作流

现状：

- `cmd_analyze` 串联采集、评分、相关性、压力测试、持仓、新闻、推荐和报告生成。
- 压力测试和推荐默认关闭，新闻关键词缓存失效时会写关键词请求并退出。
- `_attach_score_trends` 只附加上次分数、分数变化和历史峰值回撤。

问题：

- 趋势预测没有作为独立 Layer 输出，导致报告层无法稳定消费。
- `scores`、`news_data`、`holdings_data`、`correlations` 没有统一汇总为“决策证据包”。
- 快照只保存规则评分和简要指标，不保存 `feature_matrix`、趋势、Agent overlay、最终操作建议。

优化：

- 在 Layer 3 新闻分析之后、报告生成之前新增 `src/forecast/engine.py`，输出每只基金的 `trend_matrix`。
- 新增 `src/decision/engine.py`，把评分、趋势、持仓、相关性、新闻催化、用户风险偏好合成为 `operation_advice`。
- `_save_snapshot` 扩展保存 `feature_matrix`、`trend_matrix`、`operation_advice`，支持后续回测和评分校准。

建议新增输出结构：

```json
{
  "fund_code": "017436",
  "score_matrix": {},
  "feature_matrix": {},
  "trend_matrix": {
    "short_term": {"direction": "up|flat|down", "score": 0.62, "confidence": 0.58, "horizon_days": 10},
    "mid_term": {"direction": "flat", "score": 0.51, "confidence": 0.44, "horizon_days": 60},
    "drivers": ["净值动量改善", "新闻催化偏正", "估值拥挤约束"]
  },
  "operation_advice": {
    "action": "hold|buy|reduce|pause_dca|resume_dca|switch",
    "target_weight": 0.18,
    "adjust_amount": -1200,
    "confidence": 0.61,
    "triggers": []
  }
}
```

### 2.2 评分模块 `src/analysis/scorer.py`

现状：

- 宏观 20 分、中观 30 分、微观 50 分。
- 宏观和中观主要按 `fund_type`、`fund_name` 启发式打分。
- 微观使用经理存在性、Sharpe、最大回撤、机构持有等规则。
- Sortino、HHI、Alpha、IR、Beta 放入 `feature_matrix`，但没有系统性进入评分。

问题：

- “Alpha 持续性”实际使用的是 `sharpe_3y`，命名与含义不一致。
- 宏观分没有利率、汇率、指数估值、市场风险偏好等真实特征。
- 中观分没有行业动量、估值分位、拥挤度、盈利预期或政策催化。
- 微观没有区分主动基金、指数基金、QDII、债基、商品基金的评分口径。
- C/D 完整度基金把宏观 + 微观按 70 分折算到 100 分，可能放大不完整数据的信号。

优化评分体系：

1. 把评分拆为“原始特征 -> 标准化子分 -> 权重汇总 -> 置信度折扣”。
2. 每个子分保留 `value`、`score`、`weight`、`source`、`missing_policy`，避免只给总分。
3. 宏观分引入可观测数据：
   - QDII：美元指数、10Y 美债、纳指/标普估值代理、人民币汇率波动。
   - 国内权益：沪深300/创业板/中证全指趋势、市场成交额、北向/南向资金、信用利差。
   - 债券/固收：中债利率、信用利差、久期风险。
4. 中观分引入：
   - 行业 20/60/120 日动量。
   - 行业相对宽基强弱。
   - 行业新闻催化均值和扩散度。
   - 持仓 HHI 与重仓股拥挤度。
5. 微观分引入：
   - 1Y/3Y Sharpe、Sortino、Calmar、最大回撤恢复天数。
   - Jensen Alpha、IR、Beta、跟踪误差。
   - 基金经理任期、规模变化、机构持有人变化、换手率。
   - 持有人结构和规模过大/过小惩罚。
6. 完整度不要简单折算总分，应增加 `score_confidence`：
   - A：0.90-1.00
   - B：0.75-0.90
   - C：0.45-0.70
   - D：不输出买入建议，只允许“观察/数据不足”。

建议权重：

| 维度 | 当前 | 建议 | 说明 |
|------|------|------|------|
| 宏观 | 20% | 15%-25% 动态 | 对 QDII、债基提高宏观权重；主动权益可维持 20% |
| 中观 | 30% | 25%-35% 动态 | 行业/主题基金提高中观权重，均衡混合降低 |
| 微观 | 50% | 40%-55% 动态 | 主动基金提高微观权重，指数基金降低经理相关项 |

建议 `scoring_matrix`：

```json
{
  "quant_baseline": {
    "macro": {"score": 13.2, "confidence": 0.78, "factors": []},
    "meso": {"score": 18.5, "confidence": 0.70, "factors": []},
    "micro": {"score": 33.8, "confidence": 0.86, "factors": []},
    "raw_total": 65.5,
    "confidence_adjusted_total": 59.8
  },
  "agent_overlay": {
    "macro_adjustment": -2,
    "meso_adjustment": 3,
    "micro_adjustment": 0,
    "total_adjustment": 1,
    "overlay_rationale": "海外流动性压制宏观分，但产业催化改善中观趋势"
  },
  "final_score": 60.8,
  "final_confidence": 0.76
}
```

### 2.3 趋势预测模块

现状：

- 新闻催化已有 `weighted_catalyst_score` 和 `trend`。
- 评分趋势已有 `previous_score`、`score_delta`、`peak_score`、`drop_from_peak`。
- 持仓有周收益贡献、XIRR、定投状态。
- 相关性只输出 Pearson 矩阵。

问题：

- 没有独立预测 horizon：1-2 周、1-3 月、3-6 月混在报告文本。
- 没有把趋势预测转为可比较分数。
- 没有回测预测是否有效。

建议新增 `forecast` 层：

- `price_momentum_score`：20/60/120 日收益、均线斜率、最大回撤修复率。
- `risk_regime_score`：波动率分位、下行波动、Sortino 变化、Beta 上升/下降。
- `news_catalyst_score`：新闻催化均值、正负事件扩散度、事件置信度、时间衰减。
- `fundamental_proxy_score`：重仓股所在行业景气、盈利预期代理、政策事件。
- `flow_crowding_score`：成交热度、基金规模变化、机构持有变化、同主题拥挤度。

趋势评分公式建议：

```text
short_term_trend =
  0.35 * price_momentum_score
  + 0.25 * news_catalyst_score
  + 0.20 * risk_regime_score
  + 0.10 * flow_crowding_score
  + 0.10 * score_delta_signal

mid_term_trend =
  0.25 * price_momentum_score
  + 0.20 * news_catalyst_score
  + 0.25 * fundamental_proxy_score
  + 0.20 * risk_regime_score
  + 0.10 * valuation_pressure_score
```

趋势输出规则：

| 趋势分 | 方向 | 建议含义 |
|--------|------|----------|
| >= 0.65 | 上行 | 可考虑恢复/加速定投，回调买入 |
| 0.45-0.65 | 震荡 | 持有，按触发条件操作 |
| < 0.45 | 下行 | 暂停新增，减仓或等待确认 |

置信度规则：

- 样本不足、新闻少、持仓缺失、基准指数缺失时降低置信度。
- 趋势分与风险分矛盾时降低置信度，例如动量强但 Sortino 恶化。
- Agent overlay 不应改变原始趋势分，只能在 `final_view` 中解释偏离原因。

### 2.4 新闻与催化模块

现状：

- `run_news_pipeline` 构建实体画像，合并 Agent 关键词与重仓关键词。
- `compute_catalyst_score` 计算新闻事件、影响、相关度和时间衰减。
- `aggregate_fund_brief` 已输出 `weighted_catalyst_score`、`trend`、`top_events`。

问题：

- `sentiment_mean` 和 `catalyst.weighted_score` 是两套口径，报告层主要展示旧情绪口径。
- `extract_hot_sectors` 仍读取旧字段 `events`，但当前 pipeline 输出主要是 `catalyst_news` 和 `brief`。
- 低相关性新闻虽然可以由 Agent 判断，但规则层没有强制“相关度低则不进入趋势预测”。

优化：

- 统一新闻口径为 `catalyst_brief`，旧 `sentiment_mean` 仅作兼容展示。
- `extract_hot_sectors` 改为优先读取 `brief.sector_summary` 和 `catalyst_news[*].catalyst.weighted_score`。
- 对 `relevance < 0.2` 的新闻只保留样本，不进入趋势分。
- 增加“负向新闻密度”：最近 3 日负向高影响新闻条数 / 总高影响新闻条数。
- 报告中新增“催化贡献表”，展示每只基金短期趋势由哪些事件驱动。

### 2.5 推荐模块 `src/recommend/engine.py`

现状：

- 推荐候选按动量、热点、分散度、稳定性打分。
- 已有主题和暴露簇多样性约束。
- 与持仓相似度使用主题、风格、收益风险近似。

问题：

- `screen_funds` 只用场内排行接口，候选池可能偏 ETF/场内基金。
- 推荐分未显式接入用户风险偏好、目标仓位缺口、当前组合防守缺口。
- 热点行业读取旧新闻结构，可能低估新催化模块的信号。
- 推荐结果没有“买入方式”：一次性、分批、只观察、替换哪只基金。

优化：

- 候选池拆为：防守固收、红利低波、宽基底仓、成长进攻、海外分散、商品对冲。
- `rank_recommendations` 加入组合缺口：
  - 当前缺少防守资产，提高 `defensive_income/value_dividend`。
  - 当前成长制造过高，降低同簇候选。
  - 当前 QDII pending 高，降低海外新增权重。
- 推荐输出新增：
  - `replace_candidates`：建议替换/对冲的现有基金。
  - `entry_plan`：一次性/三段买入/只观察。
  - `risk_budget_impact`：加入后组合波动和相关性变化。

### 2.6 持仓与定投模块

现状：

- 事件驱动计算引擎已较完整，持仓真源为 YAML 交易流水。
- 已支持 pending、QDII T+2、XIRR、校准警告。

问题：

- 操作建议未充分利用持仓成本、浮盈浮亏、pending、定投状态。
- 定投建议目前主要由 Agent 填充，没有规则层证据包。

优化：

- 为每只基金生成 `position_context`：
  - 当前权重、目标权重、超配/低配。
  - 成本安全垫：当前净值相对平均成本、定投均线、止损线距离。
  - 流动性状态：pending 金额、确认日期、QDII 汇率风险。
  - 定投状态：是否启用、下次金额、最近 4 期执行结果。
- 定投建议规则：
  - `final_score >= 70` 且 `short_term_trend >= 0.55`：维持或加速。
  - `final_score 55-70` 且趋势震荡：维持原额。
  - `final_score < 55` 或趋势下行且亏损扩大：暂停。
  - 高相关重复敞口超阈值：只保留评分/趋势更优的一只定投。

### 2.7 相关性与组合风险

现状：

- 只计算 Pearson 相关系数，阈值 > 0.85 标记。

问题：

- 相关性没有进入仓位建议。
- 没有组合层风险预算、边际风险贡献、行业/币种/资产类别暴露。

优化：

- 输出 `portfolio_risk_matrix`：
  - 相关性矩阵。
  - 每只基金边际风险贡献。
  - 暴露簇权重：成长制造、海外、商品、防守、红利、宽基。
  - 单基金权重上限和同簇权重上限。
- 仓位建议先满足组合约束，再做单基金建议：
  - 单基金不超过 `strategy.rebalance.max_single_position`。
  - 高相关基金合计不超过 35%-40%。
  - QDII pending 高时，暂缓海外加仓。

### 2.8 报告输出模块

现状：

- `generate_report` 输出 Markdown，占位符由 Agent 填充。
- 有 `agent_decisions` 入口，但 analyze 流程未真正生成或校验该 JSON。
- 报告展示规则分、持仓、相关性、压力测试、新闻、推荐。

问题：

- 机器可校验字段不足，Agent 文本质量依赖 prompt。
- 操作建议表里的建议占比、金额、操作仍是 `AGENT_FILL`。
- `feature_matrix` 没有系统展示，导致高阶指标难以被用户审阅。

优化：

- 新增“量化评分拆解表”：
  - 每只基金展示 Macro/Meso/Micro 子因子、分数、置信度、缺失项。
- 新增“趋势预测与操作矩阵”：
  - 短期趋势、中期趋势、置信度、主要驱动、建议动作、目标仓位、调整金额。
- 新增“触发条件表”：
  - 价格/净值触发、评分触发、趋势触发、新闻触发、仓位触发。
- 把 `operation_advice` 作为结构化数据先生成，再由报告层渲染，Agent 只负责解释原因，不负责算目标仓位。

## 3. 操作建议决策框架

建议把操作建议分为两层：

### 3.1 规则决策层

输入：

- `final_score`
- `score_confidence`
- `short_term_trend`
- `mid_term_trend`
- `risk_score`
- `current_weight`
- `target_band`
- `correlation_cluster`
- `pending_amount`
- `dca_status`

输出：

| 条件 | 动作 |
|------|------|
| 高分 + 趋势上行 + 权重低于目标 | 分批加仓 / 加速定投 |
| 高分 + 趋势震荡 + 权重合理 | 持有 / 维持定投 |
| 中分 + 趋势下行 | 暂停新增 / 等待确认 |
| 低分 + 趋势下行 + 高相关重复 | 减仓 / 替换 |
| 数据置信度低 | 观察 / 不新增 |
| pending 高且 QDII | 暂缓新增，等待确认 |

### 3.2 Agent 裁量层

Agent 只允许在 `[-10, +10]` 的 overlay 里修改评分，并必须写入：

- 调整方向。
- 使用的证据。
- 与规则分歧的原因。
- 置信度。
- 触发条件。

Agent 不应直接覆盖底层事实数据，也不应在没有结构化依据时给出大额调仓。

## 4. 建议实施优先级

### P0：先把输出结构补齐

- 新增 `trend_matrix` 和 `operation_advice` 数据结构。
- 报告新增“趋势预测与操作矩阵”。
- `agent_score_context` 增加 `feature_matrix`、`position_context`、`trend_matrix`。
- 快照保存 `feature_matrix` 和最终建议。

收益：不用大改数据源，就能显著提升报告稳定性和可执行性。

### P1：重构评分基准

- 把宏观/中观/微观拆成因子表。
- 让 Sortino、Alpha、IR、Beta、HHI 真正进入微观和中观评分。
- 引入 `score_confidence`，避免 C/D 数据被过度解释。
- 增加基金类型差异化评分模板。

收益：解决“规则分看起来像结论但证据不足”的核心问题。

### P2：趋势预测和回测

- 新增 `src/forecast/engine.py`。
- 用历史快照做 1 周、1 月预测命中率回测。
- 校准趋势阈值和权重。

收益：让“未来趋势评估”从文本推演变成可验证模块。

### P3：组合风险预算和推荐联动

- 新增组合风险矩阵。
- 推荐模块接入组合缺口和风险预算。
- 目标仓位由组合约束计算，不由 Agent 手填。

收益：把单基金评分变成组合层操作建议。

## 5. 测试与验收标准

建议新增测试：

- `tests/test_score_factor_matrix.py`
  - 验证每个因子有 value/score/weight/source。
  - 验证缺失数据降低 confidence，而不是静默给满分或默认中性分。
- `tests/test_forecast_engine.py`
  - 验证趋势分方向、置信度、缺失数据处理。
  - 验证新闻高相关催化会影响短期趋势，低相关新闻不影响。
- `tests/test_decision_engine.py`
  - 验证高分上行低配给加仓。
  - 验证低分下行高相关给减仓。
  - 验证 QDII pending 高时不新增海外仓。
- `tests/test_report_trend_output.py`
  - 验证报告包含趋势预测矩阵、操作建议、触发条件。
  - 验证不再出现未替换的建议占比/金额占位符。
- `tests/test_snapshot_schema.py`
  - 验证快照保存 feature/trend/advice，历史评分趋势可恢复。

验收口径：

- 任意单只基金报告必须能回答：为什么这个分数、趋势怎么看、现在做什么、什么条件改变动作。
- 任意组合报告必须能回答：哪些风险重复、目标仓位如何来、调仓金额是否守恒、pending 是否已考虑。
- 评分和趋势必须可以回测：至少保存预测方向、预测日期、未来 5/20/60 个交易日实际收益。

## 6. 推荐落地文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/analysis/scorer.py` | 修改 | 因子矩阵化、置信度折扣、类型差异化评分 |
| `src/forecast/__init__.py` | 新建 | 趋势预测模块包 |
| `src/forecast/engine.py` | 新建 | 生成 `trend_matrix` |
| `src/decision/__init__.py` | 新建 | 决策模块包 |
| `src/decision/engine.py` | 新建 | 生成 `operation_advice` |
| `src/news/pipeline.py` | 修改 | 优先输出并消费 catalyst brief |
| `src/recommend/engine.py` | 修改 | 接入组合缺口、风险预算、买入方式 |
| `src/output/report.py` | 修改 | 增加评分拆解、趋势矩阵、操作建议表 |
| `src/db/models.py` | 修改 | 保存 feature/trend/advice JSON |
| `src/db/storage.py` | 修改 | 快照读写扩展 |
| `skills/fund-analyst/SKILL.md` | 修改 | 明确 Agent 只解释结构化建议，不手算仓位 |

## 7. 最终目标形态

最终报告不应只是“基金诊断文本”，而应成为一个带证据链的操作台：

1. **评分**：量化分、Agent overlay、最终分、置信度同时展示。
2. **趋势**：短期/中期方向、分数、置信度、驱动事件清晰列出。
3. **建议**：动作、目标仓位、金额、定投策略和触发条件由结构化引擎生成。
4. **组合**：单基金建议必须服从组合风险预算、相关性和 pending 约束。
5. **复盘**：每次建议都进入快照，未来可回测命中率并校准模型。

按这个方向改造后，Agent 的职责会更清晰：不再代替代码手算仓位和分数，而是在结构化证据基础上做宏观/产业/基金经理行为的高质量解释和有限裁量。
