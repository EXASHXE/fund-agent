# News Research MCP Boundary

Network access is host-owned. The skill may call only the injected
`MCPHostAdapter`.

## Allowed

- `mcp_adapter.has_capability(...)`
- `mcp_adapter.call("financial_news", payload)`
- `mcp_adapter.call("web_search", payload)`
- converting returned dictionaries into `SoftEvidence`

## Forbidden

- direct HTTP requests;
- provider SDK imports;
- hardcoded API keys;
- hidden credentials;
- autonomous retry loops outside host policy;
- formal `Decision` or `ExecutionLedger` generation.

The adapter boundary keeps `fund-agent` host-agnostic.
