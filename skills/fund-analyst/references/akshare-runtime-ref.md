# AKShare 基金接口参考

本文件约束数据口径。默认由数据层通过 `src/data/fetcher.py` 调用 AKShare；Agent 不直接绕过 CLI 抓数，除非用户明确要求排查数据源。

## 使用原则

- 证据构建层输出的 `report.md` 是最终研判的唯一事实源。
- AKShare 接口只用于底层采集、问题定位或代码开发，不用于在报告阶段临时补编数据。
- AKShare 字段可能变化，任何接口异常都应降级为 `[数据缺失-无法评估]` 或 NAV 自算指标，不得编造。
- 新闻、评分、趋势和操作建议已经由 pipeline 串联；Agent 只解释结构化结果。

---

## 基金基本信息

```python
import akshare as ak

df = ak.fund_individual_basic_info_xq(symbol="110011")

# 返回格式通常为两列 DataFrame：item / value
# 常见 item：基金名称、基金代码、基金类型、成立日期、基金规模、管理费率、
# 托管费率、业绩比较基准、现任基金经理、基金经理任职日期、任职回报
info = dict(zip(df["item"], df["value"]))
```

用途：

- 生成 `basic`：基金名称、类型、经理、规模、成立时间。
- 支撑 `factor_matrix.macro` 的基金类型适配，以及微观经理稳定性解释。

---

## 基金净值历史

```python
df = ak.fund_open_fund_info_em(symbol="110011", indicator="单位净值走势")

# 参数：
# symbol: 6 位基金代码
# indicator: "单位净值走势" 或 "累计净值走势"
# 常见字段：净值日期、单位净值、累计净值、日增长率
```

用途：

- 计算年化波动率、最大回撤、Sharpe、Sortino。
- 在绩效接口失败时，作为最可靠的降级数据源。
- 支撑 `trend_matrix` 中净值动量和风险状态。

注意：

- QDII 基金净值通常 T+1 至 T+2 延迟。
- 净值日期不得外推；pending 份额不计入已确认份额。

---

## 基金业绩指标

```python
df = ak.fund_individual_analysis_xq(symbol="110011")

# 常见字段：今年以来、近1年、近3年、年化波动率、最大回撤、
# 夏普比率、Alpha、Beta、信息比率、跟踪误差等
```

用途：

- 支撑 `feature_matrix`：Sharpe、最大回撤、波动率、Alpha、Beta、IR。
- 支撑 `factor_matrix.micro` 的风险收益质量解释。

降级：

- 若接口返回异常或缺失，使用 NAV 自算波动率、最大回撤、Sharpe。
- Alpha、Beta、IR 无法可靠计算时，标注缺失策略，不能静默视为优秀。

---

## 基金持仓明细

```python
df = ak.fund_portfolio_hold_em(symbol="110011", date="2026")

# 参数：
# symbol: 基金代码
# date: 报告年度
# 常见字段：股票代码、股票名称、占净值比例、持股数、持仓市值
```

用途：

- 计算 HHI。
- 生成新闻关键词请求和重仓链条解释。
- 支撑中观行业/主题判断。

注意：

- 公募基金季报滞后约 1 至 1.5 个月。
- 对滞后持仓做新闻穿透时，必须说明“基于最新披露持仓”。

---

## 基金行业/资产配置

```python
df = ak.fund_portfolio_industry_allocation_em(symbol="110011", date="2026")

# 常见字段：行业名称、占净值比例
```

用途：

- 支撑中观行业暴露。
- 支撑组合风险矩阵和同簇拥挤解释。

降级：

- 行业配置缺失时，可以用前十大持仓的行业或基金名称主题代理，但必须标注 `[数据缺失-已估算]`。

---

## 基金持有人结构

```python
df = ak.fund_hold_structure_em()

# 常见字段：基金代码、报告期、机构持有比例、个人持有比例、内部持有比例
```

用途：

- 支撑微观机构持有变化解释。
- 当前若未稳定接入，不得把缺失项当成负面或正面结论。

---

## 推荐采集顺序

1. `fund_individual_basic_info_xq` 获取基金类型、经理、规模。
2. `fund_open_fund_info_em` 获取净值序列。
3. `fund_individual_analysis_xq` 获取风险收益指标。
4. `fund_portfolio_hold_em` 获取重仓。
5. `fund_portfolio_industry_allocation_em` 获取行业配置。
6. `fund_hold_structure_em` 获取持有人结构。

任一环节失败时：

- 不阻断整条分析链。
- 把缺失写入完整度和 `missing_policy`。
- 降低 `score_confidence`。
- 报告中说明缺口，不用自由文本补造。

---

## 与当前分析链路的关系

| 数据 | 进入模块 | 报告解释 |
|------|----------|----------|
| 基本信息 | `FundAnalyzer.load_fund` | 类型适配、经理稳定性 |
| 净值历史 | `feature_matrix`、`trend_matrix` | 波动率、回撤、Sortino、趋势 |
| 绩效指标 | `factor_matrix.micro` | Alpha、Beta、IR、Sharpe |
| 重仓 | 新闻关键词、HHI、中观暴露 | 新闻穿透、拥挤度 |
| 行业配置 | `portfolio_risk_matrix` | 暴露簇、组合风险预算 |
| 持有人结构 | 微观因子 | 机构资金行为 |

Agent 在报告阶段必须优先引用 EvidenceGraph 中的 HardEvidence 节点，而不是重新调用接口。
