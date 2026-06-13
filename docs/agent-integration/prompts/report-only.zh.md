# 报告模式提示词

## 输入要求

- 用户提供基金组合数据（持仓、成本等）
- 可选：provider_data_snapshot
- 可选：风险偏好和约束

## 调用方式

```
fund-agent analyze-portfolio --input portfolio.json --format markdown --output report.md
```

## 输出

- 结构化分析报告（JSON 或 Markdown）
- 不包含正式交易决策
- 不包含经纪执行指令

## 禁止

- 不调用 decision_support
- 不生成 Decision / ExecutionLedger
- 不编造缺失数据
