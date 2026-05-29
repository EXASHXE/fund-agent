---
name: fund-analysis
description: Pure quantitative fund scoring and portfolio exposure analysis — QuantRiskAnalysis + PortfolioExposureAnalysis
---

# Fund Analysis

## Contract

- **Purpose**: Pure quantitative fund scoring (Sharpe, Sortino, HHI, volatility, max drawdown) and portfolio exposure analysis via KnowledgeGraph queries
- **Inputs**: ResearchTask, KnowledgeGraph context, fund portfolio data
- **Outputs**: HardEvidence items (confidence_weight=1.0) for quant metrics and exposure analysis
- **Required MCP Capabilities**: None (pure math — no IO, no network, no LLM)
- **Priority**: 1
- **Fallback Strategy**: If KG unavailable, compute exposure from raw holdings data directly
- **Forbidden Behavior**: Do NOT hardcode API keys or vendor SDKs; Do NOT generate final BUY/SELL decisions directly; Do NOT bypass EvidenceGraph; Do NOT use LLM to compute quant metrics

---

This skill is the split implementation of the legacy `fund-analyst` umbrella.
It covers QuantRiskAnalysis and PortfolioExposureAnalysis.

See `skills/fund-analyst/SKILL.md` for the legacy umbrella (retained for reference).
