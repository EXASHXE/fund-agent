"""Eastmoney host data adapter — example / optional host adapter.

Unofficial / web endpoint provider. May work without cookies for some
endpoints; if the endpoint returns auth/captcha/blocked/empty due to
missing cookie, returns ok=False with MISSING_CREDENTIALS or PROVIDER_BLOCKED.

Must not be imported by core runtime. No provider SDK imports.
Disabled by default. Credential requirements unknown until live smoke.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


ENDPOINTS: dict[str, dict[str, Any]] = {
    "fund_nav_history": {
        "url": "https://fund.eastmoney.com/f10/F10DataApi.aspx",
        "method": "GET",
        "capability": ProviderCapability.FUND_NAV_HISTORY,
    },
    "fund_profile": {
        "url": "https://fund.eastmoney.com/js/fundcode_search.js",
        "method": "GET",
        "capability": ProviderCapability.FUND_PROFILE,
    },
    "fund_holdings": {
        "url": "https://fund.eastmoney.com/FundArchivesDatas.aspx",
        "method": "GET",
        "capability": ProviderCapability.FUND_HOLDINGS,
    },
    "fund_ranking": {
        "url": "https://fund.eastmoney.com/data/rankhandler.aspx",
        "method": "GET",
        "capability": ProviderCapability.FUND_RANKING,
    },
    "index_history": {
        "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        "method": "GET",
        "capability": ProviderCapability.INDEX_HISTORY,
    },
    "stock_quote": {
        "url": "https://push2.eastmoney.com/api/qt/stock/get",
        "method": "GET",
        "capability": ProviderCapability.STOCK_QUOTE,
    },
}

_BLOCKED_INDICATORS = [
    "captcha",
    "验证码",
    "login",
    "登录",
    "forbidden",
    "access denied",
    "请先登录",
]

_RATE_LIMIT_INDICATORS = [
    "rate limit",
    "too many requests",
    "请求过于频繁",
    "429",
]


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path}"


class EastmoneyAdapter:
    name: str = "eastmoney"
    capabilities: set[ProviderCapability] = {
        ProviderCapability.FUND_NAV_HISTORY,
        ProviderCapability.FUND_PROFILE,
        ProviderCapability.FUND_HOLDINGS,
        ProviderCapability.FUND_RANKING,
        ProviderCapability.INDEX_HISTORY,
        ProviderCapability.STOCK_QUOTE,
    }

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_name="eastmoney",
            enabled=False,
            priority=20,
            require_credentials=False,
            capabilities=[c.value for c in self.capabilities],
        )
        creds = self._config.credentials
        self._cookie = creds.cookie if creds and creds.cookie else None
        self._user_agent = (
            creds.user_agent
            if creds and creds.user_agent
            else "Mozilla/5.0 (compatible; FundAgent/1.0)"
        )

    def _build_provenance(
        self,
        endpoint_name: str,
        url: str,
        as_of: str | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed = urlparse(url)
        return {
            "source": "eastmoney",
            "endpoint_name": endpoint_name,
            "url_host": parsed.hostname,
            "as_of": as_of or date.today().isoformat(),
            "input_params": input_params or {},
        }

    def _detect_blocked(self, text: str) -> str | None:
        lower = text.lower()
        for indicator in _BLOCKED_INDICATORS:
            if indicator in lower:
                return indicator
        return None

    def _detect_rate_limited(self, text: str) -> str | None:
        lower = text.lower()
        for indicator in _RATE_LIMIT_INDICATORS:
            if indicator in lower:
                return indicator
        return None

    def _make_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": self._user_agent,
            "Referer": "https://fund.eastmoney.com/",
        }
        if self._cookie:
            headers["Cookie"] = self._cookie
        return headers

    def _credential_trace(self) -> dict[str, str]:
        return {
            "cookie": "<redacted>" if self._cookie else "<empty>",
            "user_agent": self._user_agent,
        }

    def assess_credentials_requirement(self) -> ProviderResult:
        return ProviderResult(
            ok=True,
            provider=self.name,
            capability="CREDENTIAL_ASSESSMENT",
            confidence="medium",
            freshness="fresh",
            data={
                "works_without_credentials": "unknown",
                "requires_credentials": "unknown",
                "cookie_env": "EASTMONEY_COOKIE",
                "user_agent_env": "FUND_AGENT_USER_AGENT",
                "cookie_present": bool(self._cookie),
                "note": "Credential requirements unknown until live smoke test. "
                "Some endpoints may work without cookie; others may return PROVIDER_BLOCKED.",
            },
            provenance={
                "source": "eastmoney",
                "function_name": "assess_credentials_requirement",
                "as_of": date.today().isoformat(),
            },
        )

    def health_check(self) -> ProviderResult:
        ep = ENDPOINTS["fund_profile"]
        return ProviderResult(
            ok=True,
            provider=self.name,
            capability="HEALTH_CHECK",
            confidence="high",
            freshness="fresh",
            provenance=self._build_provenance("health_check", ep["url"]),
            warnings=[] if not self._cookie else ["cookie present; some endpoints may still be blocked"],
        )

    def get_fund_nav_history(self, fund_code: str, start: str, end: str) -> ProviderResult:
        ep = ENDPOINTS["fund_nav_history"]
        if self._config.require_credentials and not self._cookie:
            return ProviderResult.missing_credentials(self.name, ProviderCapability.FUND_NAV_HISTORY)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_NAV_HISTORY)._with(
            fund_code=fund_code,
            as_of=end,
            provenance=self._build_provenance(
                "fund_nav_history",
                ep["url"],
                as_of=end,
                input_params={"fund_code": fund_code, "start": start, "end": end},
            ),
            warnings=["Eastmoney adapter is example-only; implement HTTP call in host layer"],
        )

    def get_fund_profile(self, fund_code: str) -> ProviderResult:
        ep = ENDPOINTS["fund_profile"]
        if self._config.require_credentials and not self._cookie:
            return ProviderResult.missing_credentials(self.name, ProviderCapability.FUND_PROFILE)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_PROFILE)._with(
            fund_code=fund_code,
            provenance=self._build_provenance(
                "fund_profile",
                ep["url"],
                input_params={"fund_code": fund_code},
            ),
            warnings=["Eastmoney adapter is example-only; implement HTTP call in host layer"],
        )

    def get_fund_holdings(self, fund_code: str, as_of: str | None = None) -> ProviderResult:
        ep = ENDPOINTS["fund_holdings"]
        if self._config.require_credentials and not self._cookie:
            return ProviderResult.missing_credentials(self.name, ProviderCapability.FUND_HOLDINGS)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_HOLDINGS)._with(
            fund_code=fund_code,
            as_of=as_of,
            provenance=self._build_provenance(
                "fund_holdings",
                ep["url"],
                as_of=as_of,
                input_params={"fund_code": fund_code, "as_of": as_of},
            ),
            warnings=["Eastmoney adapter is example-only; implement HTTP call in host layer"],
        )

    def get_fee_schedule(self, fund_code: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.FUND_FEE_SCHEDULE,
            fund_code=fund_code,
            errors=["NOT_SUPPORTED"],
            confidence="low",
            freshness="unknown",
        )

    def get_redemption_rules(self, fund_code: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.FUND_REDEMPTION_RULES,
            fund_code=fund_code,
            errors=["NOT_SUPPORTED"],
            confidence="low",
            freshness="unknown",
        )

    def get_stock_quote(self, symbol: str) -> ProviderResult:
        ep = ENDPOINTS["stock_quote"]
        if self._config.require_credentials and not self._cookie:
            return ProviderResult.missing_credentials(self.name, ProviderCapability.STOCK_QUOTE)
        return ProviderResult.not_implemented(self.name, ProviderCapability.STOCK_QUOTE)._with(
            symbol=symbol,
            provenance=self._build_provenance(
                "stock_quote",
                ep["url"],
                input_params={"symbol": symbol},
            ),
            warnings=["Eastmoney adapter is example-only; implement HTTP call in host layer"],
        )

    def get_fund_ranking(self, fund_type: str = "all") -> ProviderResult:
        ep = ENDPOINTS["fund_ranking"]
        if self._config.require_credentials and not self._cookie:
            return ProviderResult.missing_credentials(self.name, ProviderCapability.FUND_RANKING)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_RANKING)._with(
            provenance=self._build_provenance(
                "fund_ranking",
                ep["url"],
                input_params={"fund_type": fund_type},
            ),
            warnings=["Eastmoney adapter is example-only; implement HTTP call in host layer"],
        )


def smoke_test() -> dict[str, Any]:
    adapter = EastmoneyAdapter()
    health = adapter.health_check()
    cred = adapter.assess_credentials_requirement()
    has_cookie = bool(adapter._cookie)
    status = "OK" if health.ok else "FAILED"
    return {
        "provider": "eastmoney",
        "status": status,
        "health": health.to_dict(),
        "credential_assessment": cred.data,
        "credential_trace": adapter._credential_trace(),
    }
