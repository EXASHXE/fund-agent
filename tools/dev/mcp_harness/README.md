# Dev-only MCP Harness

This harness demonstrates how host-injected MCP responses can be transformed
into fund-agent payload artifacts. It is dev-only and must NOT be imported by
core runtime.

## Rules

- Fake mode is default
- Live mode must be env-gated (FUND_AGENT_ENABLE_LIVE_MCP=1)
- CI must not require live MCP
- No API keys in code
- No provider SDK dependencies
- No network call in tests
- Core runtime must not import this harness
- Harness outputs plain JSON fields that fund_analysis already understands

## Environment variables (live mode only)

- FUND_AGENT_ENABLE_LIVE_MCP=1
- FUND_AGENT_MCP_COMMAND
- FUND_AGENT_MCP_SERVER_URL

These are documented for reference only. Live mode is not implemented in v1.
