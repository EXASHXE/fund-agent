# Data Provider Contract — v1.7

## Core No-Network Boundary

The fund-agent core runtime (`src/skills_runtime`, `src/tools`, `src/schemas`, `src/graph`, `src/skillpack`) must never make network calls or import provider SDKs. All external data access is mediated through host-owned adapter implementations.

## Host Adapter Layer

Data providers are implemented as host-owned adapters in `examples/host_data_adapters/` or host-specific packages. These adapters:

- May import provider SDKs (e.g., akshare) inside the adapter module only
- Must return `ProviderResult` with provenance metadata
- Must handle missing credentials gracefully with `MISSING_CREDENTIALS`
- Must never be imported by core runtime

## Provider Result Schema

Every provider call returns a `ProviderResult` with:

| Field | Type | Description |
|-------|------|-------------|
| ok | bool | Whether the call succeeded |
| provider | str | Provider name |
| capability | str | Capability that was called |
| symbol | str \| None | Stock/fund symbol |
| fund_code | str \| None | Fund code |
| as_of | str \| None | Data as-of date |
| freshness | str | "fresh", "stale", or "unknown" |
| confidence | str | "high", "medium", or "low" |
| data | dict \| list \| None | Normalized response data |
| warnings | list[str] | Non-fatal warnings |
| errors | list[str] | Error codes (MISSING_CREDENTIALS, PROVIDER_BLOCKED, etc.) |
| provenance | dict | Source, function_name, as_of, input_params |
| raw_sample | dict \| list \| str \| None | Optional raw response sample |

## Provider Config Schema

Provider configuration is defined in `config/providers.example.yaml`:

| Field | Type | Description |
|-------|------|-------------|
| provider_name | str | Unique provider identifier |
| enabled | bool | Whether provider is active |
| priority | int | Lower = higher priority |
| timeout_seconds | float | Request timeout |
| rate_limit_per_minute | int \| None | Rate limit |
| credentials | ProviderCredentials | API key, token, cookie (env var names) |
| cache_ttl_seconds | int \| None | Cache TTL |
| require_credentials | bool | Whether credentials are required |
| allowed_domains | list[str] | Domain whitelist |
| compliance_notes | list[str] | Compliance documentation |
| capabilities | list[str] | Supported capabilities |

## Credentials Policy

- All credentials are loaded from environment variables or host config
- No API keys, cookies, or tokens may be committed to the repository
- `ProviderCredentials.redacted()` replaces all credential values with `<redacted>`
- Providers requiring credentials that are missing must fail with `MISSING_CREDENTIALS`
- Environment variable names (e.g., `XUEQIU_COOKIE`) are documented in config, not actual values

## AkShare Role

- Primary public data source for fund NAV, profile, holdings, index history, stock history
- Generally does not require API keys for basic endpoints
- `require_credentials: false` by default
- May require `user_agent` env var in some cases
- Adapter lives in `examples/host_data_adapters/akshare_adapter.py`

## Eastmoney Role

- Supplementary fund NAV, profile, holdings, ranking, index history, stock quote
- Unofficial/web endpoint provider — not an officially supported API
- Cookie requirements are unknown and must be verified by smoke tests
- If an endpoint requires a cookie and none is configured: `MISSING_CREDENTIALS`
- Adapter lives in `examples/host_data_adapters/eastmoney_adapter.py`

## Xueqiu Role

- Optional stock quote and social sentiment supplement
- Likely requires cookie/token for most endpoints
- `require_credentials: true` by default
- Must not be used as authoritative fund NAV source
- Adapter lives in `examples/host_data_adapters/xueqiu_adapter.py`

## News MCP/API Key Policy

- news-research skill uses host-injected MCP capabilities (`web_search`, `financial_news`)
- These MCP capabilities may require API keys from the host
- Supported environment variables: `NEWS_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY`, `SERPAPI_API_KEY`, `CUSTOM_NEWS_MCP_TOKEN`
- fund-agent core must not know or hardcode these credentials
- News provider failures should become: `MISSING_MCP_CAPABILITY`, `MISSING_CREDENTIALS`, `MCP_CALL_FAILED`, `EMPTY_RESULT`, or `PARTIAL`

## Fallback Policy

When multiple providers support the same capability, the fallback policy (`src/host_data/fallback_policy.py`) selects providers by:

1. Only enabled providers
2. Filtered by capability
3. Sorted by priority (lower = higher priority)
4. Preferred providers rank first if enabled and capable

The fallback policy returns provider names only, not data. The host decides how to execute the fallback chain.

## Reconciliation Policy

When multiple providers return data for the same query, `compare_provider_results()` detects discrepancies:

- **CONSISTENT**: All valid results agree (or only one valid result with SINGLE_SOURCE warning)
- **DIVERGENT**: Results disagree beyond tolerance (>1% for numeric values)
- **INSUFFICIENT**: No valid results

The reconciliation does NOT average or fabricate data. It reports discrepancies as warnings that can feed into evidence gaps.

## Provider Provenance

Every provider-derived data item must include:
- `source`: Provider name
- `provenance`: Dict with function_name, endpoint_name, url_host, as_of, input_params
- `as_of`: Date the data was current
- `freshness`: "fresh", "stale", or "unknown"

Missing provenance should generate warnings in the quality gate.

## Compliance Notes

- Eastmoney and Xueqiu adapters access unofficial endpoints. Hosts must verify compliance with terms of service.
- No scraping of pages in a brittle way unless isolated and clearly marked experimental.
- Rate limits must be respected.
- Data must not be redistributed without verifying licensing.
