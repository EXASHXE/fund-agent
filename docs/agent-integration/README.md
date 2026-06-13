# Agent Integration Guide

How external code agents should use fund-agent correctly with the public API, portfolio input pack, provider snapshot, and markdown report flow.

## Core Principles

- **fund-agent is a skill pack, not an autonomous agent**
- Core runtime is **no-network** and **no-provider-SDK**
- Provider adapters are **optional host-layer examples**
- Credentials come from **config/env only** — never committed
- Only `decision_support` may produce formal `Decision` / `ExecutionLedger`

## Flows

### Report-Only Flow

When user asks: "怎么看", "分析一下", "风险如何", "是否需要观察"

1. Run `fund_analysis` skill
2. Build `final_report` from artifacts
3. Render markdown if requested
4. **Do not call `decision_support`**

### Soft Action Advice Flow

When user asks: "怎么办", "是否先观望", "给个操作思路"

1. Run `fund_analysis` skill
2. May provide non-formal analysis
3. **Do not emit Decision / ExecutionLedger**
4. Action boundary must be clear

### Formal Trade Decision Flow

When user asks: "今天卖出/买入/减仓/加仓多少", "正式决策", "给交易计划"

1. Run `fund_analysis` skill first
2. Build evidence graph if enough evidence
3. Run `decision_support` only with sufficient evidence
4. Active trades require evidence anchors
5. Output audit artifacts only
6. **Never place or fulfill orders**

### Provider Data Flow

1. Host collects live data via adapter
2. Host builds `provider_data_snapshot`
3. fund-agent consumes snapshot
4. Core does not fetch

### Private Data Flow

1. Never commit real data
2. Use `local_data/` / `private_data/` / `local_reports/`
3. Sanitize outputs before sharing
