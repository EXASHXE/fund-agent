"""Xueqiu host data adapter — example / optional host adapter.

Optional stock quote / social sentiment supplement.
Requires cookie and token; disabled by default.
Never commits cookies/tokens; redacts credentials in trace and errors.

Must not be imported by core runtime. No provider SDK imports.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any
from urllib.parse import urlparse

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


ENDPOINTS: dict[str, dict[str, Any]] = {
    "stock_quote": {
        "url": "https://stock.xueqiu.com/v5/stock/quote.json",
        "method": "GET",
        "capability": ProviderCapability.STOCK_QUOTE,
    },
    "stock_history": {
        "url": "https://stock.xueqiu.com/v5/stock/chart/kline.json",
        "method": "GET",
        "capability": ProviderCapability.STOCK_HISTORY,
    },
    "social_sentiment": {
        "url": "https://xueqiu.com/statuses/search.json",
        "method": "GET",
        "capability": ProviderCapability.SOCIAL_SENTIMENT,
    },
}

_AUTH_INDICATORS = [
    "login",
    "登录",
    "captcha",
    "验证码",
    "需要登录",
]

_RATE_LIMIT_INDICATORS = [
    "rate limit",
    "too many requests",
    "请求过于频繁",
    "429",
]

_BLOCKED_INDICATORS = [
    "forbidden",
    "access denied",
    "blocked",
    "禁止访问",
    "403",
]


def _redact_credential(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "***redacted***"
    return value[:3] + "***redacted***" + value[-3:]


class XueqiuAdapter:
    name: str = "xueqiu"
    capabilities: set[ProviderCapability] = {
        ProviderCapability.STOCK_QUOTE,
        ProviderCapability.STOCK_HISTORY,
        ProviderCapability.SOCIAL_SENTIMENT,
    }

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_name="xueqiu",
            enabled=False,
            priority=30,
            require_credentials=True,
            capabilities=[c.value for c in self.capabilities],
        )
        self._cookie = os.environ.get("XUEQIU_COOKIE")
        self._token = os.environ.get("XUEQIU_TOKEN")
        self._user_agent = os.environ.get(
            "FUND_AGENT_USER_AGENT",
            "Mozilla/5.0 (compatible; FundAgent/1.0)",
        )

    def _has_credentials(self) -> bool:
        return bool(self._cookie and self._token)

    def _require_credentials(self, capability: str) -> ProviderResult | None:
        if not self._cookie or not self._token:
            return ProviderResult.missing_credentials(self.name, capability)
        return None

    def _build_provenance(
        self,
        endpoint_name: str,
        url: str,
        as_of: str | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed = urlparse(url)
        return {
            "source": "xueqiu",
            "endpoint_name": endpoint_name,
            "url_host": parsed.hostname,
            "as_of": as_of or date.today().isoformat(),
            "input_params": input_params or {},
            "credentials_present": self._has_credentials(),
        }

    def _detect_response_issue(self, text: str) -> ProviderResult | None:
        lower = text.lower()
        for indicator in _AUTH_INDICATORS:
            if indicator in lower:
                return ProviderResult.provider_auth_required(self.name, "RESPONSE_CHECK")
        for indicator in _RATE_LIMIT_INDICATORS:
            if indicator in lower:
                return ProviderResult.provider_rate_limited(self.name, "RESPONSE_CHECK")
        for indicator in _BLOCKED_INDICATORS:
            if indicator in lower:
                return ProviderResult.provider_blocked(self.name, "RESPONSE_CHECK", reason="blocked_indicator_detected")
        return None

    def _make_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": self._user_agent,
            "Referer": "https://xueqiu.com/",
        }
        if self._cookie:
            headers["Cookie"] = self._cookie
        if self._token:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return headers

    def _credential_trace(self) -> dict[str, str]:
        return {
            "cookie": _redact_credential(self._cookie),
            "token": _redact_credential(self._token),
            "user_agent": self._user_agent,
        }

    def health_check(self) -> ProviderResult:
        if not self._has_credentials():
            return ProviderResult.missing_credentials(self.name, "HEALTH_CHECK")
        ep = ENDPOINTS["stock_quote"]
        return ProviderResult(
            ok=True,
            provider=self.name,
            capability="HEALTH_CHECK",
            confidence="high",
            freshness="fresh",
            provenance=self._build_provenance("health_check", ep["url"]),
        )

    def get_stock_quote(self, symbol: str) -> ProviderResult:
        missing = self._require_credentials(ProviderCapability.STOCK_QUOTE)
        if missing:
            return missing
        ep = ENDPOINTS["stock_quote"]
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.STOCK_QUOTE,
            symbol=symbol,
            errors=["NOT_IMPLEMENTED"],
            confidence="low",
            freshness="unknown",
            provenance=self._build_provenance(
                "stock_quote",
                ep["url"],
                input_params={"symbol": symbol},
            ),
            warnings=["Xueqiu adapter is example-only; implement HTTP call in host layer"],
        )

    def get_stock_history(self, symbol: str, start: str, end: str) -> ProviderResult:
        missing = self._require_credentials(ProviderCapability.STOCK_HISTORY)
        if missing:
            return missing
        ep = ENDPOINTS["stock_history"]
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.STOCK_HISTORY,
            symbol=symbol,
            as_of=end,
            errors=["NOT_IMPLEMENTED"],
            confidence="low",
            freshness="unknown",
            provenance=self._build_provenance(
                "stock_history",
                ep["url"],
                as_of=end,
                input_params={"symbol": symbol, "start": start, "end": end},
            ),
            warnings=["Xueqiu adapter is example-only; implement HTTP call in host layer"],
        )

    def get_social_sentiment(self, keyword: str) -> ProviderResult:
        missing = self._require_credentials(ProviderCapability.SOCIAL_SENTIMENT)
        if missing:
            return missing
        ep = ENDPOINTS["social_sentiment"]
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.SOCIAL_SENTIMENT,
            errors=["NOT_IMPLEMENTED"],
            confidence="low",
            freshness="unknown",
            provenance=self._build_provenance(
                "social_sentiment",
                ep["url"],
                input_params={"keyword": keyword},
            ),
            warnings=["Xueqiu adapter is example-only; implement HTTP call in host layer"],
        )


def smoke_test() -> dict[str, Any]:
    adapter = XueqiuAdapter()
    health = adapter.health_check()
    has_cookie = bool(adapter._cookie)
    has_token = bool(adapter._token)
    if not has_cookie or not has_token:
        status = "SKIPPED"
        reason_parts = []
        if not has_cookie:
            reason_parts.append("XUEQIU_COOKIE not set")
        if not has_token:
            reason_parts.append("XUEQIU_TOKEN not set")
        reason = "; ".join(reason_parts)
    elif health.ok:
        status = "OK"
        reason = None
    else:
        status = "FAILED"
        reason = str(health.errors)
    return {
        "provider": "xueqiu",
        "status": status,
        "health": health.to_dict(),
        "credential_assessment": {
            "cookie_present": has_cookie,
            "token_present": has_token,
            "cookie_required": True,
            "token_required": True,
            "enabled_by_default": False,
            "reason": reason,
        },
        "credential_trace": adapter._credential_trace(),
    }
