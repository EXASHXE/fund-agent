# 正式决策模式提示词

## 输入要求

- analysis_mode: formal_trade_decision
- 完整的组合数据
- 充分的证据数据
- 风险偏好和约束

## 调用方式

```
fund-agent analyze-portfolio --input portfolio.json --format markdown --output report.md
```

## 输出

- 分析报告
- 正式 Decision（如证据充分）
- ExecutionLedger
- 证据锚定说明

## 禁止

- 不执行经纪操作
- 不编造证据
- 不绕过质量门控
