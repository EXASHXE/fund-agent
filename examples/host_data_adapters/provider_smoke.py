"""Provider smoke test runner — opt-in live smoke checks for host adapters.

Not imported by core runtime. Network is allowed only here and in adapter examples.
Must be opt-in. Must print ProviderResult redacted. Must never print
cookies/tokens/API keys.

Usage:
    python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001
    python examples/host_data_adapters/provider_smoke.py --provider eastmoney --capability FUND_NAV_HISTORY --fund-code 000001 --resolve-env
    python examples/host_data_adapters/provider_smoke.py --provider xueqiu --capability STOCK_QUOTE --symbol SH000001 --resolve-env
    python examples/host_data_adapters/provider_smoke.py --all --resolve-env --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.host_data.provider_config import ProviderConfig, ProviderCredentialSpec, ProviderCredentials, resolve_credentials_from_env
from src.host_data.provider_result import ProviderResult

PROVIDER_STATUS: dict[str, dict[str, Any]] = {
    "akshare": {
        "works_without_credentials": True,
        "requires_credentials": False,
    },
    "eastmoney": {
        "works_without_credentials": "unknown",
        "requires_credentials": "unknown",
        "cookie_env": "EASTMONEY_COOKIE",
        "user_agent_env": "FUND_AGENT_USER_AGENT",
    },
    "xueqiu": {
        "works_without_credentials": "unknown",
        "requires_credentials": "likely",
        "cookie_env": "XUEQIU_COOKIE",
        "token_env": "XUEQIU_TOKEN",
    },
}


def _redact_result(d: dict[str, Any]) -> dict[str, Any]:
    out = dict(d)
    for key in ("data", "raw_sample"):
        if key in out and out[key] is not None:
            out[key] = f"<{key} omitted>"
    provenance = out.get("provenance")
    if isinstance(provenance, dict):
        redacted_prov = {}
        for k, v in provenance.items():
            if isinstance(v, str) and any(
                kw in k.lower() for kw in ("cookie", "token", "api_key", "authorization", "bearer")
            ):
                redacted_prov[k] = "<redacted>"
            else:
                redacted_prov[k] = v
        out["provenance"] = redacted_prov
    return out


def _run_provider_smoke(
    provider: str,
    capability: str,
    resolve_env: bool = False,
    fund_code: str | None = None,
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    status_info = PROVIDER_STATUS.get(provider, {})
    result: dict[str, Any] = {
        "provider": provider,
        "capability": capability,
        "works_without_credentials": status_info.get("works_without_credentials", "unknown"),
        "requires_credentials": status_info.get("requires_credentials", "unknown"),
    }

    config = ProviderConfig(
        provider_name=provider,
        enabled=True,
        credential_spec=ProviderCredentialSpec(
            api_key_env=status_info.get("api_key_env"),
            token_env=status_info.get("token_env"),
            cookie_env=status_info.get("cookie_env"),
            user_agent_env=status_info.get("user_agent_env"),
        ),
    )

    credentials = ProviderCredentials()
    if resolve_env:
        credentials = resolve_credentials_from_env(config.credential_spec, env=env)
    config.credentials = credentials

    try:
        if provider == "akshare":
            from akshare_adapter import AkShareAdapter
            adapter = AkShareAdapter(config=config)
        elif provider == "eastmoney":
            from eastmoney_adapter import EastmoneyAdapter
            adapter = EastmoneyAdapter(config=config)
        elif provider == "xueqiu":
            from xueqiu_adapter import XueqiuAdapter
            adapter = XueqiuAdapter(config=config)
        else:
            result["status"] = "SKIPPED"
            result["reason"] = f"unknown provider: {provider}"
            return result
    except ImportError as exc:
        result["status"] = "SKIPPED"
        result["reason"] = f"MISSING_DEPENDENCY: {exc}"
        return result

    if not credentials.has_any() and status_info.get("requires_credentials") in (True, "likely"):
        if not resolve_env:
            result["status"] = "SKIPPED"
            result["reason"] = "credentials not resolved; use --resolve-env"
            return result

    try:
        if capability == "HEALTH_CHECK":
            pr = adapter.health_check()
        elif capability == "FUND_NAV_HISTORY":
            pr = adapter.get_fund_nav_history(fund_code=fund_code or "000001", start=start or "20240101", end=end or "20241231")
        elif capability == "FUND_PROFILE":
            pr = adapter.get_fund_profile(fund_code=fund_code or "000001")
        elif capability == "FUND_HOLDINGS":
            pr = adapter.get_fund_holdings(fund_code=fund_code or "000001")
        elif capability == "STOCK_QUOTE":
            pr = adapter.get_stock_quote(symbol=symbol or "SH000001")
        elif capability == "STOCK_HISTORY":
            pr = adapter.get_stock_history(symbol=symbol or "SH000001", start=start or "20240101", end=end or "20241231")
        elif capability == "SOCIAL_SENTIMENT":
            pr = adapter.get_social_sentiment(keyword=symbol or "fund")
        else:
            result["status"] = "SKIPPED"
            result["reason"] = f"unsupported capability: {capability}"
            return result
    except Exception as exc:
        result["status"] = "FAILED"
        result["reason"] = str(exc)
        return result

    pr_dict = pr.to_dict()
    redacted = _redact_result(pr_dict)

    if pr.ok:
        result["status"] = "OK"
    elif "MISSING_CREDENTIALS" in pr.errors:
        result["status"] = "MISSING_CREDENTIALS"
    elif "MISSING_DEPENDENCY" in pr.errors:
        result["status"] = "SKIPPED"
        result["reason"] = "MISSING_DEPENDENCY"
    elif "NOT_IMPLEMENTED" in pr.errors:
        result["status"] = "NOT_IMPLEMENTED"
    elif "PROVIDER_AUTH_REQUIRED" in pr.errors:
        result["status"] = "PROVIDER_AUTH_REQUIRED"
    elif "PROVIDER_RATE_LIMITED" in pr.errors:
        result["status"] = "PROVIDER_RATE_LIMITED"
    elif "PROVIDER_BLOCKED" in pr.errors:
        result["status"] = "PROVIDER_BLOCKED"
    else:
        result["status"] = "FAILED"

    result["provider_result"] = redacted
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Provider smoke test runner")
    parser.add_argument("--provider", choices=["akshare", "eastmoney", "xueqiu"], help="Provider to test")
    parser.add_argument("--all", action="store_true", help="Test all providers")
    parser.add_argument("--capability", default="HEALTH_CHECK", help="Capability to test")
    parser.add_argument("--fund-code", default=None, help="Fund code for fund capabilities")
    parser.add_argument("--symbol", default=None, help="Symbol for stock capabilities")
    parser.add_argument("--start", default=None, help="Start date")
    parser.add_argument("--end", default=None, help="End date")
    parser.add_argument("--resolve-env", action="store_true", help="Resolve credentials from environment")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    providers = ["akshare", "eastmoney", "xueqiu"] if args.all else [args.provider]
    if not providers or providers == [None]:
        parser.error("Specify --provider or --all")

    results: list[dict[str, Any]] = []
    for provider in providers:
        if provider is None:
            continue
        r = _run_provider_smoke(
            provider=provider,
            capability=args.capability,
            resolve_env=args.resolve_env,
            fund_code=args.fund_code,
            symbol=args.symbol,
            start=args.start,
            end=args.end,
        )
        results.append(r)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            status = r.get("status", "UNKNOWN")
            provider = r.get("provider", "?")
            print(f"[{status}] {provider}")
            if r.get("reason"):
                print(f"  reason: {r['reason']}")
            print(f"  works_without_credentials: {r.get('works_without_credentials', 'unknown')}")
            print(f"  requires_credentials: {r.get('requires_credentials', 'unknown')}")
            pr = r.get("provider_result")
            if pr:
                print(f"  result: ok={pr.get('ok')}, errors={pr.get('errors')}, warnings={pr.get('warnings')}")

    has_failure = any(r.get("status") in ("FAILED", "PROVIDER_AUTH_REQUIRED", "PROVIDER_BLOCKED") for r in results)
    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
