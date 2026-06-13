"""AkShare host data adapter — example / optional host adapter.

May import akshare inside this example adapter only.
Must not be imported by core runtime.
Handles ImportError gracefully with MISSING_DEPENDENCY.
No credentials required by default for basic public endpoints.
"""

from __future__ import annotations

from datetime import date
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

    def assess_credentials_requirement(self) -> ProviderResult:
        return ProviderResult(
            ok=True,
            provider=self.name,
            capability="CREDENTIAL_ASSESSMENT",
            confidence="high",
            freshness="fresh",
            data={
                "works_without_credentials": True,
                "requires_credentials": False,
                "auth_type": "none",
                "note": "AkShare basic public endpoints generally do not require credentials",
            },
            provenance={
                "source": "akshare",
                "function_name": "assess_credentials_requirement",
                "as_of": date.today().isoformat(),
            },
        )

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
            provenance={
                "source": "akshare",
                "function_name": "health_check",
                "as_of": date.today().isoformat(),
            },
        )

    def get_fund_nav_history(self, fund_code: str, start: str, end: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_NAV_HISTORY)
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            expected_cols = {"净值日期", "单位净值", "日增长率"}
            if hasattr(df, "columns"):
                actual_cols = set(str(c) for c in df.columns)
                if not expected_cols.intersection(actual_cols):
                    return ProviderResult.unexpected_schema(
                        self.name,
                        ProviderCapability.FUND_NAV_HISTORY,
                        expected=expected_cols,
                        actual=actual_cols,
                    )._with(fund_code=fund_code, as_of=end, provenance={
                        "source": "akshare",
                        "function_name": "fund_open_fund_info_em",
                        "as_of": end,
                        "input_params": {"fund_code": fund_code, "indicator": "单位净值走势"},
                    })
            records = df.to_dict("records") if hasattr(df, "to_dict") else []
            if not records:
                return ProviderResult.empty_result(self.name, ProviderCapability.FUND_NAV_HISTORY)._with(
                    fund_code=fund_code, as_of=end, provenance={
                        "source": "akshare",
                        "function_name": "fund_open_fund_info_em",
                        "as_of": end,
                        "input_params": {"fund_code": fund_code, "indicator": "单位净值走势"},
                    },
                )
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
                    "input_params": {"fund_code": fund_code, "indicator": "单位净值走势"},
                },
            )
        except Exception as exc:
            return ProviderResult.network_error(
                self.name, ProviderCapability.FUND_NAV_HISTORY, reason=str(exc)
            )._with(fund_code=fund_code, as_of=end, provenance={
                "source": "akshare",
                "function_name": "fund_open_fund_info_em",
                "as_of": end,
                "input_params": {"fund_code": fund_code, "start": start, "end": end},
            })

    def get_fund_profile(self, fund_code: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_PROFILE)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_PROFILE)._with(
            fund_code=fund_code,
            warnings=["get_fund_profile is not yet implemented for akshare adapter"],
            provenance={
                "source": "akshare",
                "function_name": "get_fund_profile",
                "as_of": date.today().isoformat(),
                "input_params": {"fund_code": fund_code},
            },
        )

    def get_fund_holdings(self, fund_code: str, as_of: str | None = None) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.FUND_HOLDINGS)
        return ProviderResult.not_implemented(self.name, ProviderCapability.FUND_HOLDINGS)._with(
            fund_code=fund_code,
            as_of=as_of,
            warnings=["get_fund_holdings is not yet implemented for akshare adapter"],
            provenance={
                "source": "akshare",
                "function_name": "get_fund_holdings",
                "as_of": as_of or date.today().isoformat(),
                "input_params": {"fund_code": fund_code, "as_of": as_of},
            },
        )

    def get_index_history(self, symbol: str, start: str, end: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.INDEX_HISTORY)
        return ProviderResult.not_implemented(self.name, ProviderCapability.INDEX_HISTORY)._with(
            symbol=symbol,
            as_of=end,
            warnings=["get_index_history is not yet implemented for akshare adapter"],
            provenance={
                "source": "akshare",
                "function_name": "get_index_history",
                "as_of": end,
                "input_params": {"symbol": symbol, "start": start, "end": end},
            },
        )

    def get_stock_history(self, symbol: str, start: str, end: str) -> ProviderResult:
        ak = self._ensure_akshare()
        if ak is None:
            return ProviderResult.missing_dependency(self.name, ProviderCapability.STOCK_HISTORY)
        return ProviderResult.not_implemented(self.name, ProviderCapability.STOCK_HISTORY)._with(
            symbol=symbol,
            as_of=end,
            warnings=["get_stock_history is not yet implemented for akshare adapter"],
            provenance={
                "source": "akshare",
                "function_name": "get_stock_history",
                "as_of": end,
                "input_params": {"symbol": symbol, "start": start, "end": end},
            },
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
    cred = adapter.assess_credentials_requirement()
    if not health.ok:
        return {
            "provider": "akshare",
            "status": "SKIPPED",
            "reason": "akshare not installed",
            "credential_assessment": cred.data,
        }
    return {
        "provider": "akshare",
        "status": "OK",
        "health": health.to_dict(),
        "credential_assessment": cred.data,
    }
