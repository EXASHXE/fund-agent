"""AkShare host data adapter — example / optional host adapter.

May import akshare inside this example adapter only.
Must not be imported by core runtime.
Handles ImportError gracefully with MISSING_DEPENDENCY.
"""

from __future__ import annotations

from typing import Any

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


class AkShareAdapter:
    name: str = "akshare"
    capabilities: set[ProviderCapability] = {
        ProviderCapability.FUND_NAV_HISTORY,
        ProviderCapability.FUND_PROFILE,
        ProviderCapability.FUND_HOLDINGS,
        ProviderCapability.INDEX_HISTORY,
        ProviderCapability.STOCK_HISTORY,
    }

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_name="akshare",
            enabled=True,
            priority=10,
            require_credentials=False,
            capabilities=[c.value for c in self.capabilities],
        )
        self._akshare = None

    def _ensure_akshare(self) -> Any:
        if self._akshare is not None:
            return self._akshare
        try:
            import akshare as _ak
            self._akshare = _ak
            return _ak
        except ImportError:
            return None

    def health_check(self) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, "HEALTH_CHECK")
        return ProviderResult(
            ok=True,
            provider=self.name,
            capability="HEALTH_CHECK",
            confidence="high",
            freshness="fresh",
        )

    def get_fund_nav_history(self, fund_code: str, start: str, end: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_NAV_HISTORY)
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            records = df.to_dict("records") if hasattr(df, "to_dict") else []
            return ProviderResult(
                ok=True,
                provider=self.name,
                capability=ProviderCapability.FUND_NAV_HISTORY,
                fund_code=fund_code,
                as_of=end,
                freshness="fresh",
                confidence="high",
                data=records,
                provenance={
                    "source": "akshare",
                    "function_name": "fund_open_fund_info_em",
                    "as_of": end,
                    "input_params": {"fund_code": fund_code, "start": start, "end": end},
                },
            )
        except Exception as exc:
            return ProviderResult(
                ok=False,
                provider=self.name,
                capability=ProviderCapability.FUND_NAV_HISTORY,
                fund_code=fund_code,
                errors=[str(exc)],
                confidence="low",
                freshness="unknown",
            )

    def get_fund_profile(self, fund_code: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_PROFILE)
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.FUND_PROFILE,
            fund_code=fund_code,
            errors=["NOT_IMPLEMENTED"],
            confidence="low",
            freshness="unknown",
            warnings=["get_fund_profile is not yet implemented for akshare adapter"],
        )

    def get_fund_holdings(self, fund_code: str, as_of: str | None = None) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_HOLDINGS)
        return ProviderResult(
            ok=False,
            provider=self.name,
            capability=ProviderCapability.FUND_HOLDINGS,
            fund_code=fund_code,
            errors=["NOT_IMPLEMENTED"],
            confidence="low",
            freshness="unknown",
            warnings=["get_fund_holdings is not yet implemented for akshare adapter"],
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


def smoke_test() -> dict[str, Any]:
    adapter = AkShareAdapter()
    health = adapter.health_check()
    if not health.ok:
        return {"provider": "akshare", "status": "SKIPPED", "reason": "akshare not installed"}
    return {"provider": "akshare", "status": "OK", "health": health.to_dict()}
