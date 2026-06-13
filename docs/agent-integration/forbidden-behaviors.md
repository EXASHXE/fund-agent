# Forbidden Behaviors

Agents using fund-agent must NOT:

1. **Execute trades** — no broker API calls, no order placement
2. **Fetch live data in core runtime** — all provider access is host-layer
3. **Import provider SDKs in core** — akshare, tavily, etc. stay in host adapters
4. **Commit secrets** — no API keys, cookies, tokens in repo
5. **Commit real portfolio data** — use local_data/ only
6. **Fabricate evidence** — missing data must be disclosed, not invented
7. **Bypass quality gate** — quality gate failures must be surfaced
8. **Generate formal decisions without evidence** — active trades require anchors
9. **Call decision_support for report-only flows** — only when formal decision is requested
10. **Use LLM for report generation** — report renderer is deterministic
11. **Claim production provider support** — adapters are prototypes
12. **Bypass fee/redemption checks** — always check before sell recommendations
