# AKShare 基金接口参考

> 以下为经过验证的 AKShare 基金相关接口。agent 必须使用这些接口获取数据，不得编造函数名。

---

## 基金基本信息

```python
import akshare as ak

# 获取基金基本信息（成立时间、规模、经理、费率等）
df = ak.fund_individual_basic_info_xq(symbol="110011")

# 返回格式：两列 DataFrame（item / value）
# item 示例: 基金名称, 基金代码, 基金类型, 成立日期, 基金规模, 管理费率,
# 托管费率, 业绩比较基准, 现任基金经理, 基金经理任职日期, 任职回报
info = dict(zip(df["item"], df["value"]))
```

## 基金净值历史

```python
# 获取基金历史净值（日频）
df = ak.fund_open_fund_info_em(symbol="110011", indicator="单位净值走势")

# 参数: symbol(基金代码), indicator("单位净值走势" 或 "累计净值走势")
# 返回字段: 净值日期, 单位净值, 累计净值, 日增长率
# 注意: QDII 基金净值有 T+1 至 T+2 延迟
```

## 基金业绩指标

```python
# 获取基金风险收益指标（夏普、Alpha、Beta、最大回撤等）
df = ak.fund_individual_analysis_xq(symbol="110011")

# 返回字段: 今年以来, 近1年, 近3年, 年化波动率, 最大回撤,
# 夏普比率, Alpha, Beta, 信息比率, 跟踪误差 等
```

## 基金持仓明细

```python
# 获取基金前十大重仓股
df = ak.fund_portfolio_hold_em(symbol="110011", date="2026")

# 参数: symbol(基金代码), date(报告年度)
# 返回字段: 股票代码, 股票名称, 占净值比例, 持股数, 持仓市值
# 注意: 公募基金季报滞后约 1-1.5 个月
```

## 基金行业/资产配置

```python
# 获取行业配置
df = ak.fund_portfolio_industry_allocation_em(symbol="110011", date="2026")

# 返回字段: 行业名称, 占净值比例
```

## 基金持有人结构

```python
# 获取持有人结构（机构/个人比例）
df = ak.fund_hold_structure_em()

# 返回字段: 基金代码, 报告期, 机构持有比例, 个人持有比例, 内部持有比例
```

---

## 获取策略建议

### 优先级

1. 先调用 `fund_individual_basic_info_xq` 获取基金类型、经理信息
2. 再调用 `fund_open_fund_info_em` 获取完整净值序列
3. 然后调用 `fund_individual_analysis_xq` 获取现成风险指标
4. 最后尝试 `fund_portfolio_hold_em` 和持仓相关接口

### 容错

- 任一接口超时或报错，记录日志后根据降级表回退
- QDII 基金注意净值延迟标注
- 基金代码非 6 位数字时，提示用户确认代码

### 注意

- AKShare 接口名称和返回格式可能随版本更新而变
- 部分接口返回 pandas DataFrame，需正确处理 NaN 值
