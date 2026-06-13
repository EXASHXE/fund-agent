# 真实数据分析提示词

## 安全规则

- 真实组合数据仅存放在 local_data/
- 生成报告仅存放在 local_reports/
- 不提交真实数据到代码仓库
- 分享前必须脱敏

## 流程

1. 复制模板到 local_data/
2. 填入真实数据
3. 运行 fund-agent analyze-portfolio --input local_data/portfolio.json
4. 输出到 local_reports/
5. 分享前脱敏

## 禁止

- 不提交真实持仓金额
- 不提交真实基金代码与金额的关联
- 不提交 provider cookies/tokens
