# 安全边界提示词

## 核心边界

1. **无网络** — core runtime 不做网络调用
2. **无 Provider SDK** — core 不导入 akshare/tavily 等
3. **无经纪执行** — 不下单、不交易
4. **无 LLM 生成** — 报告由确定性引擎生成
5. **无自主交易** — 不自动执行任何操作

## 数据边界

- 凭证仅从 config/env 读取
- 不提交 API keys/cookies/tokens
- 真实数据仅存放在 local_data/
- 缺失数据必须披露，不可编造

## 决策边界

- fund_analysis = 分析/报告 only
- decision_support = 唯一正式 Decision 来源
- suggested_rebalance_plan = 分析 only
- 报告模式不调用 decision_support
