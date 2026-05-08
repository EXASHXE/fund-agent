# AKShare 基金接口参考

> 以下为经过验证的 AKShare 基金相关接口。agent 必须使用这些接口获取数据，不得编造函数名。

---

## 基金基本信息

```python
import akshare as ak

# 获取基金基本信息（成立时间、规模、费率、类型等）
ak.fund_basic_info(fund_code="110011")

# 返回字段示例：
# fund_name, fund_code, fund_type, inception_date, fund_size, management_fee,
# custodian_fee, benchmark, current_manager, manager_start_date, manager_tenure_return
```

## 基金净值历史

```python
# 获取基金历史净值（日频）
ak.fund_open_fund_info_em(fund="110011", indicator="单位净值走势")

# 参数: fund(基金代码), indicator(可选: 单位净值走势/累计净值走势/累计收益率走势)
# 返回: date, net_value, accumulated_net_value, daily_return
# 注意: QDII 基金净值有 T+1 至 T+2 延迟
```

## 基金业绩指标

```python
# 获取基金风险收益指标（夏普、Alpha、Beta、最大回撤等）
ak.fund_performance_evaluation(fund="110011")

# 返回字段: 基金代码, 今年以来, 近1周, 近1月, 近3月, 近6月, 近1年, 近2年,
# 近3年, 成立以来, 年化波动率, 最大回撤, Sharpe(年化), Alpha(年化), Beta,
# 信息比率, 下行风险, 索提诺比率
```

## 基金持仓明细

```python
# 获取基金持仓（前十大重仓股/债）
ak.fund_portfolio_hold_detail_em(fund="110011", year="2026")

# 参数: fund(基金代码), year(报告年度)
# 返回字段: 序号, 股票代码, 股票名称, 占净值比例%, 持股数, 持仓市值, 季度
# 注意: 公募基金季报滞后约 1-1.5 个月，最新数据可能为上个季度
```

## 基金行业配置

```python
# 获取基金资产配置
ak.fund_portfolio_asset_allocation(fund="110011", year="2026")

# 返回字段: 类别, 占净值比例%
# 包含: 股票, 债券, 现金, 其他资产
```

## 基金持有人结构

```python
# 获取基金持有人结构（机构/个人比例）
ak.fund_holder_structure(fund="110011")

# 返回字段: 报告期, 机构持有比例%, 个人持有比例%, 内部持有比例%
```

---

## 获取策略建议

### 优先级
1. 先调用 `fund_basic_info` 获取基金类型、经理信息
2. 再调用 `fund_open_fund_info_em` 获取完整净值序列
3. 然后调用 `fund_performance_evaluation` 获取现成风险指标
4. 最后尝试 `fund_portfolio_hold_detail_em` 和持仓相关接口

### 容错
- 任一接口超时或报错，记录日志后根据降级表回退
- QDII 基金优先使用 `fund_performance_evaluation` 中的现成数据，避免自行估算
- 基金代码非 6 位数字时，提示用户确认代码

### 注意
- AKShare 接口名称和返回格式可能随版本更新而变。若接口报错 `AttributeError` 或 `ModuleNotFoundError`，优先检查 AKShare 版本：`ak.__version__`
- 部分接口返回 pandas DataFrame，需正确处理 NaN 值
