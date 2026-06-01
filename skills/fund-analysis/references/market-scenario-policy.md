# Market Scenario Policy

Market scenario handling is host-owned. `fund-agent` does not fetch or invent
market regimes, crash scenarios, drawdown assumptions, or macro narratives.

## Accepted Scenario Shape

```json
{
  "name": "risk_off_june_drawdown",
  "risk_level": "high",
  "description": "Host-provided scenario text"
}
```

## Runtime Behavior

- Include scenario flags only when `market_scenario` is supplied.
- Treat high-risk scenarios as risk flags.
- Emit scenario HardEvidence only from host-provided scenario content.
- If absent, do not create scenario conclusions.

## Report Language

```text
市场情景：本段仅基于主机提供的 risk_off_june_drawdown 情景，不代表 fund-agent 自行抓取或判断市场状态。
```
