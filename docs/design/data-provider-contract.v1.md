# Data Provider Contract — v1.7.1

## Core No-Network Boundary

The fund-agent core runtime (`src/skills_runtime`, `src/tools`, `src/schemas`, `src/graph`, `src/skillpack`) must never make network calls or import provider SDKs. All external data access is mediated through host-owned adapter implementations.

## Host Adapter Layer

Data providers are implemented as host-owned adapters in `examples/host_data_adapters/` or host-specific packages. These adapters:

- May import provider SDKs (e.g., akshare) inside the adapter module only
- Must return `ProviderResult` with provenance metadata
- Must handle missing credentials gracefully with `MISSING_CREDENTIALS`
- Must never be imported by core runtime
- Are optional host layer, not core runtime

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
| credential_spec | ProviderCredentialSpec | Env var names for credentials (safe to log/commit) |
| credentials | ProviderCredentials | Resolved secret values (never logged/committed) |
| cache_ttl_seconds | int \| None | Cache TTL |
| require_credentials | bool | Whether credentials are required |
| allowed_domains | list[str] | Domain whitelist |
| compliance_notes | list[str] | Compliance documentation |
| capabilities | list[str] | Supported capabilities |

## ProviderCredentialSpec vs ProviderCredentials

`ProviderCredentialSpec` stores environment variable names. It is safe to log, commit, and display.

| Field | Type | Description |
|-------|------|-------------|
| api_key_env | str \| None | Env var name for API key |
| token_env | str \| None | Env var name for token |
| cookie_env | str \| None | Env var name for cookie |
| user_agent_env | str \| None | Env var name for user agent |
| extra_header_envs | dict[str, str] | Env var names for extra headers |
| extra_envs | dict[str, str] | Env var names for extra credentials |

`ProviderCredentials` stores resolved secret values. It must never be logged, committed, or displayed in full.

| Field | Type | Description |
|-------|------|-------------|
| api_key | str \| None | Resolved API key value |
| token | str \| None | Resolved token value |
| cookie | str \| None | Resolved cookie value |
| user_agent | str \| None | Resolved user agent value |
| extra_headers | dict[str, str] | Resolved extra header values |
| extra | dict[str, str] | Resolved extra credential values |

## Credential Resolution Flow

1. `providers.example.yaml` contains env var names only (e.g., `cookie_env: XUEQIU_COOKIE`).
2. `load_provider_configs(resolve_env=False)` loads env names into `ProviderCredentialSpec`, leaves `ProviderCredentials` empty.
3. `load_provider_configs(resolve_env=True, env=...)` resolves values from env mapping into `ProviderCredentials`.
4. `resolve_credentials_from_env(spec, env=...)` resolves credentials from a mapping (testable with fake env).
5. `credentials_missing(config)` detects missing required credentials.
6. Empty strings are treated as missing.
7. `user_agent` alone does not count as authentication credential.
8. Adapters read credentials from `config.credentials`, not from `os.environ` directly.
9. `to_dict()` and `redacted()` never expose real credential values.

## Credentials Policy

- All credentials are loaded from environment variables or host config
- No API keys, cookies, or tokens may be committed to the repository
- `ProviderCredentials.redacted()` replaces all credential values with `<redacted>`
- Providers requiring credentials that are missing must fail with `MISSING_CREDENTIALS`
- Environment variable names (e.g., `XUEQIU_COOKIE`) are documented in config, not actual values
- `ProviderCredentialSpec.to_dict()` shows env var names (safe)
- `ProviderConfig.to_dict()` shows `credential_spec` env names and `credentials` redacted

## Provider Smoke Runner

The provider smoke runner (`examples/host_data_adapters/provider_smoke.py`) runs optional live smoke checks:

```bash
python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001
python examples/host_data_adapters/provider_smoke.py --provider eastmoney --capability FUND_NAV_HISTORY --fund-code 000001 --resolve-env
python examples/host_data_adapters/provider_smoke.py --provider xueqiu --capability STOCK_QUOTE --symbol SH000001 --resolve-env
python examples/host_data_adapters/provider_smoke.py --all --resolve-env --json
```

- Not imported by core runtime
- Network is allowed only here and in adapter examples
- Must be opt-in
- Must print ProviderResult redacted
- Must never print cookies/tokens/API keys
- Returns nonzero if provider fails unexpectedly
- Missing optional dependency or missing credentials returns SKIPPED/MISSING_CREDENTIALS status
- Documents `works_without_credentials` and `requires_credentials` per provider

## AkShare Role

- Primary public data source for fund NAV, profile, holdings, index history, stock history
- **Currently only FUND_NAV_HISTORY is implemented; all other capabilities return NOT_IMPLEMENTED**
- Generally does not require API keys for basic endpoints
- `require_credentials: false` by default
- `works_without_credentials: true`
- `requires_credentials: false`
- May require `user_agent` env var in some cases
- Adapter lives in `examples/host_data_adapters/akshare_adapter.py`
- FUND_NAV_HISTORY is implemented; other capabilities return NOT_IMPLEMENTED
- Handles missing akshare dependency with MISSING_DEPENDENCY
- Validates expected columns defensively
- **Provider snapshot is the recommended path for real testing**

## Eastmoney Role

- Supplementary fund NAV, profile, holdings, ranking, index history, stock quote
- Unofficial/web endpoint provider — not an officially supported API
- **Prototype scaffold only — host must implement HTTP calls or run live smoke to verify**
- `works_without_credentials: unknown` (not verified by live smoke)
- `requires_credentials: unknown` (not verified by live smoke)
- Cookie requirements are unknown and must be verified by smoke tests
- `cookie_env: EASTMONEY_COOKIE`, `user_agent_env: FUND_AGENT_USER_AGENT`
- If an endpoint requires a cookie and none is configured: `MISSING_CREDENTIALS`
- If response indicates auth/captcha/rate-limit/blocked: `PROVIDER_AUTH_REQUIRED`, `PROVIDER_BLOCKED`, or `PROVIDER_RATE_LIMITED`
- Adapter lives in `examples/host_data_adapters/eastmoney_adapter.py`
- All capabilities currently return NOT_IMPLEMENTED (endpoint map defined)
- `assess_credentials_requirement()` returns current credential status

## Xueqiu Role

- Optional stock quote and social sentiment supplement
- Likely requires cookie/token for most endpoints
- **Prototype scaffold only — host must implement HTTP calls or run live smoke to verify**
- `works_without_credentials: unknown` (not verified by live smoke)
- `requires_credentials: likely`
- `require_credentials: true` by default
- `cookie_env: XUEQIU_COOKIE`, `token_env: XUEQIU_TOKEN`
- Must not be used as authoritative fund NAV source
- Disabled by default
- If no cookie/token is provided and endpoint requires auth: `MISSING_CREDENTIALS`
- If response indicates login/captcha/rate-limit: `PROVIDER_AUTH_REQUIRED`, `PROVIDER_RATE_LIMITED`, or `PROVIDER_BLOCKED`
- Adapter lives in `examples/host_data_adapters/xueqiu_adapter.py`
- All capabilities currently return NOT_IMPLEMENTED
- `assess_credentials_requirement()` returns current credential status

## Cookie/API-Key Investigation Workflow

1. Run `provider_smoke.py --provider <name> --capability HEALTH_CHECK` without credentials.
2. If the response is blocked/auth-required, set the relevant env var and re-run with `--resolve-env`.
3. Document findings in `works_without_credentials` and `requires_credentials`.
4. Do not claim stable no-cookie access unless smoke test proves it.

## News MCP/API Key Policy

- news-research skill uses host-injected MCP capabilities (`web_search`, `financial_news`)
- These MCP capabilities may require API keys from the host
- Supported environment variables: `NEWS_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY`, `SERPAPI_API_KEY`, `CUSTOM_NEWS_MCP_TOKEN`
- fund-agent core must not know or hardcode these credentials
- News provider failures should map to: `MISSING_MCP_CAPABILITY`, `MISSING_CREDENTIALS`, `MCP_CALL_FAILED`, `EMPTY_RESULT`, or `PARTIAL`
- News MCP credentials are documented in `config/providers.example.yaml` under `news_mcp`
- news-research SKILL.md points to data-provider-contract and providers.example.yaml

## No-Secrets Policy

- No real API keys, cookies, or tokens may be committed
- Config files use env var names only (e.g., `cookie_env: XUEQIU_COOKIE`)
- `ProviderCredentials.redacted()` replaces all values with `<redacted>`
- `ProviderConfig.to_dict()` shows credential_spec env names and credentials redacted
- Trace, gate, and JSON output must redact all credential values
- Adapter examples must not log full cookie/token values
- Boundary tests scan for committed secrets (cookie-like, token-like, API key-like values)

## Adapter Examples Are Optional Host Layer

- Adapter examples live in `examples/host_data_adapters/`
- They are NOT imported by core runtime
- They may import provider SDKs (e.g., akshare) inside the adapter module only
- They are optional; hosts may implement their own adapters
- Network-enabled adapter examples must remain under `examples/host_data_adapters/` or a clearly optional host-adapter package

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
