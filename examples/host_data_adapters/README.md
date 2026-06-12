# Host Data Adapters

Example / optional host-owned data provider adapters. These are NOT imported by core runtime.

## Provider Status

| Provider     | Default enabled | Credentials                                | Capabilities                 | Notes                        |
| ------------ | --------------: | ------------------------------------------ | ---------------------------- | ---------------------------- |
| AkShare      |          yes/no | usually none for basic public examples     | fund/nav/index/stock history | optional dependency          |
| Eastmoney    |              no | unknown/optional cookie depending endpoint | fund/nav/ranking/quote       | unofficial/web endpoint risk |
| Xueqiu       |              no | likely cookie/token for many endpoints     | stock quote/social sentiment | optional supplement          |
| News MCP/API |              no | API key/token by provider                  | news/search                  | host-owned MCP               |

## Credential Assessment

| Provider  | works_without_cookie | requires_cookie | Notes |
|-----------|---------------------|-----------------|-------|
| AkShare   | yes                 | no              | Basic public endpoints generally do not require credentials |
| Eastmoney | unknown             | unknown         | Adapter must verify whether selected endpoints work without cookies |
| Xueqiu    | unknown             | likely yes      | Do not assume public no-cookie access |

Run `python provider_smoke.py` to test actual connectivity.

## Architecture

- Adapters may import provider SDKs (e.g., akshare) inside the adapter module only.
- Core runtime (`src/`) must never import these adapters or provider SDKs.
- All adapters return `ProviderResult` with provenance metadata.
- Missing credentials produce `MISSING_CREDENTIALS` error, not crashes.
- No API keys, cookies, or tokens may be committed.
