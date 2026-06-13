# Development Testing Guide

## Default test command

```bash
PYTHONPATH=. pytest -q
```

This runs all tests except live provider tests. No network, no provider SDKs, no API keys required.

## Targeted test commands

```bash
PYTHONPATH=. pytest tests/release -q
PYTHONPATH=. pytest tests/public_api -q
PYTHONPATH=. pytest tests/docs -q
PYTHONPATH=. pytest tests/architecture -q
PYTHONPATH=. pytest tests/host_data -q
PYTHONPATH=. pytest tests/contracts -q
PYTHONPATH=. pytest tests/skills_runtime -q
PYTHONPATH=. pytest tests/personal_regression -q
PYTHONPATH=. pytest tests/workflow -q
PYTHONPATH=. pytest tests/install -q
PYTHONPATH=. pytest tests/scripts -q
```

## Live provider smoke tests

Live provider tests require real dependencies and/or network access. They are **opt-in** and **skipped by default**.

To enable:

```bash
FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1 PYTHONPATH=. pytest tests/host_data/test_live_provider_adapters.py -q
```

To run the provider smoke script:

```bash
python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001
python examples/host_data_adapters/provider_smoke.py --provider eastmoney --capability FUND_NAV_HISTORY --fund-code 000001 --resolve-env
python examples/host_data_adapters/provider_smoke.py --provider xueqiu --capability STOCK_QUOTE --symbol SH000001 --resolve-env
```

> **Warning:** Do not run live provider smoke in CI unless credentials/network are intentionally configured.

## How to avoid leaking credentials

- Provider credentials are read from config/env only — never committed.
- `ProviderCredentialSpec` stores env var names (safe to log/commit).
- `ProviderCredentials` stores resolved values (never logged/committed).
- `to_dict()` and `redacted()` never expose real credential values.
- Provider smoke runner redacts all credential fields in output.

## Expected behavior when optional dependencies are missing

- **AkShare not installed**: adapter returns `MISSING_DEPENDENCY` error; tests use mocks.
- **Eastmoney cookie not set**: adapter returns `MISSING_CREDENTIALS` when `require_credentials=True`; otherwise proceeds with no cookie.
- **Xueqiu cookie/token not set**: adapter returns `MISSING_CREDENTIALS` for all endpoints.
- **npm not available**: install tests skip.
- **build module not installed**: build tests skip.

## Test markers

| Marker | Purpose | Default behavior |
|--------|---------|-----------------|
| `live_provider` | Requires live provider access | Skipped unless `FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1` |
| `adapter_live` | Requires real adapter dependency | Skipped unless enabled |
| `slow` | Slow end-to-end tests | Runs by default |
| `subprocess` | Spawns subprocesses | Runs by default |
| `install` | Packaging/install tests | Runs by default |
| `regression` | Personal regression tests | Runs by default |
