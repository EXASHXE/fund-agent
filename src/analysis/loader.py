"""Fund data loading and completeness assessment."""
from __future__ import annotations

import pandas as pd

from src.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure,
)


class FundDataLoader:
    def load_fund(self, code: str) -> dict:
        basic = fetch_fund_basic(code)
        perf = fetch_fund_performance(code)
        nav = fetch_fund_nav(code)
        holdings = fetch_fund_holdings(code)
        sectors = fetch_fund_sectors(code)
        holders = fetch_holder_structure(code)

        fund_data = {
            "basic": basic,
            "perf": perf,
            "nav": nav,
            "holdings": holdings,
            "sectors": sectors,
            "holders": holders,
        }

        completeness = self._assess_completeness(basic, perf, nav, holdings, sectors)
        fund_data["completeness"] = completeness
        return fund_data

    def _assess_completeness(self, basic, perf, nav, holdings, sectors) -> str:
        has_basic = bool(basic) and "error" not in basic
        has_nav = isinstance(nav, pd.DataFrame) and len(nav) > 30
        has_perf = bool(perf) and "error" not in perf

        if not has_basic or not has_nav:
            return "D"

        core_ok = has_basic and has_nav
        enhanced_ok = (
            isinstance(holdings, pd.DataFrame) and len(holdings) > 0 and
            isinstance(sectors, pd.DataFrame) and len(sectors) > 0
        )

        if not core_ok:
            return "D"
        if has_perf and enhanced_ok:
            return "A"
        if has_perf:
            return "B"
        if core_ok and enhanced_ok:
            return "B"
        if core_ok:
            return "C"
        return "D"
