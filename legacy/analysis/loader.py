"""Fund data loading and completeness assessment."""
from __future__ import annotations

import pandas as pd

from src.infra.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure,
)
from src.tools.scoring.helpers import assess_completeness


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
        """Delegate to pure function in src.tools.scoring.helpers."""
        return assess_completeness(basic, perf, nav, holdings, sectors)
