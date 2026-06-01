# Sentiment Signal Quality Policy

Sentiment is soft evidence. It should supplement deterministic fund and
portfolio analysis, not override it.

## Stronger Signals

- timestamped and source-attributed;
- mapped to specific funds, holdings, sectors, or themes;
- supported by volume, breadth, or confidence fields;
- consistent across multiple host-approved sources.

## Weaker Signals

- low volume;
- unclear entity mapping;
- bot-prone or spam-prone channels;
- stale social chatter;
- sentiment without source metadata.

## Reporting

Hosts should phrase sentiment as uncertainty-aware:

```text
情绪信号偏负面，但属于 SoftEvidence；它提示短期波动风险，不能单独构成卖出结论。
```
