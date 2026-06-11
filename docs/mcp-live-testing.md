# MCP Live Testing (Dev-Only)

This document describes how MCP live testing can be configured for development
purposes only. Live MCP testing is NOT required for CI and is NOT part of the
core runtime.

## Fake mode (default)

The fake MCP harness at `tools/dev/mcp_harness/` provides static JSON responses
that simulate MCP provider outputs. No network calls, no credentials, no API keys.

```bash
python tools/dev/mcp_harness/normalize_mcp_responses.py
```

## Live mode (env-gated, not implemented in v1)

Live mode would connect to real MCP providers to fetch live fund data.
It requires environment variables and is intended for manual development testing only.

Required environment variables:
- `FUND_AGENT_ENABLE_LIVE_MCP=1`
- `FUND_AGENT_MCP_COMMAND` or `FUND_AGENT_MCP_SERVER_URL`

## Rules

- Fake mode is the default and only mode in v1
- CI must not require live MCP
- No API keys in source code
- No provider SDK dependencies
- Core runtime must not import the harness
- Harness outputs must be plain JSON compatible with fund_analysis payload fields
