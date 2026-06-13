# Host Data Adapters

Example / optional host-owned data provider adapters. These are NOT imported by core runtime.

## Provider Status

| Provider | Default | Credentials | Current implementation | Live smoke | Notes |
| -------- | ------: | ----------- | ---------------------- | ---------- | ----- |
| AkShare | enabled | none required | FUND_NAV_HISTORY implemented; others NOT_IMPLEMENTED | not tested | Broad coverage fallback; optional dependency |
| Eastmoney | disabled | unknown (cookie_env: EASTMONEY_COOKIE) | All NOT_IMPLEMENTED (endpoint map defined) | not tested | Unofficial/web endpoint; disabled by default |
| Xueqiu | disabled | likely required (cookie_env: XUEQIU_COOKIE, token_env: XUEQIU_TOKEN) | All NOT_IMPLEMENTED | not tested | Stock quote/sentiment supplement; disabled by default |
| News MCP/API | disabled | API key by provider (NEWS_API_KEY, TAVILY_API_KEY, EXA_API_KEY, SERPAPI_API_KEY, CUSTOM_NEWS_MCP_TOKEN) | Host-owned MCP | not tested | Host owns MCP provider and credentials |

## Credential Assessment

| Provider | works_without_credentials | requires_credentials | cookie_env | token_env | Notes |
|----------|--------------------------|---------------------|------------|-----------|-------|
| AkShare | true | false | — | — | Basic public endpoints generally do not require credentials |
| Eastmoney | unknown | unknown | EASTMONEY_COOKIE | — | Adapter must verify whether selected endpoints work without cookies |
| Xueqiu | unknown | likely | XUEQIU_COOKIE | XUEQIU_TOKEN | Do not assume public no-cookie access |

## Smoke Testing

Run the provider smoke runner to test connectivity:

```bash
python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001
python examples/host_data_adapters/provider_smoke.py --provider eastmoney --capability FUND_NAV_HISTORY --fund-code 000001 --resolve-env
python examples/host_data_adapters/provider_smoke.py --provider xueqiu --capability STOCK_QUOTE --symbol SH000001 --resolve-env
python examples/host_data_adapters/provider_smoke.py --all --resolve-env --json
```

All smoke tests are opt-in and skip by default if credentials or dependencies are missing.

> **Warning:** Do not run live provider smoke in CI unless credentials/network are
> intentionally configured. Provider smoke may perform network calls and requires
> real provider dependencies. It is outside core runtime and opt-in only.

## Architecture

- Adapters may import provider SDKs (e.g., akshare) inside the adapter module only.
- Core runtime (`src/`) must never import these adapters or provider SDKs.
- All adapters return `ProviderResult` with provenance metadata.
- Missing credentials produce `MISSING_CREDENTIALS` error, not crashes.
- No API keys, cookies, or tokens may be committed.
- `ProviderCredentialSpec` stores env var names (safe to log/commit).
- `ProviderCredentials` stores resolved secret values (never logged/committed).
- `resolve_credentials_from_env(spec, env=...)` resolves credentials from a mapping (testable with fake env).
- `credentials_missing(config)` detects missing required credentials.
- `assess_credentials_requirement()` on each adapter returns credential status.

## Credential Resolution Flow

1. Load `providers.example.yaml` with `load_provider_configs(resolve_env=False)` → env names in `credential_spec`, no resolved values.
2. Optionally call `load_provider_configs(resolve_env=True, env=...)` → resolved values in `credentials`.
3. Pass `ProviderConfig` with resolved `credentials` to adapter constructor.
4. Adapters read credentials from `config.credentials`, not from `os.environ` directly.
5. `to_dict()` and `redacted()` never expose real credential values.
