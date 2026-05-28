"""Micro scoring (weight: 50/100). Manager quality + Alpha persistence + drawdown + Sharpe + institutional holdings."""
from typing import Dict, Tuple


class MicroScorer:
    def score(self, code: str, fund_data: dict) -> Tuple[int, Dict, str]:
        fund = fund_data
        basic = fund["basic"]
        perf = fund.get("perf", {})
        details = {}

        perf_3y = perf.get("近3年", {})
        perf_1y = perf.get("近1年", {})
        ftype = basic.get("fund_type", "")

        manager_name = basic.get("manager", "")
        if manager_name:
            manager_score = 8
            details["manager"] = manager_name
        else:
            manager_score = 5

        sharpe_3y = perf_3y.get("sharpe_ratio", 0) or 0
        if sharpe_3y > 1.5:
            alpha_score = 11
        elif sharpe_3y > 1.0:
            alpha_score = 9
        elif sharpe_3y > 0.5:
            alpha_score = 7
        elif sharpe_3y > 0:
            alpha_score = 4
        else:
            alpha_score = 3

        max_dd = perf_3y.get("max_drawdown", 30) or 30
        if "QDII" in ftype:
            peer_dd = 28
        elif "指数" in ftype or "ETF" in ftype:
            peer_dd = 30
        else:
            peer_dd = 22

        if max_dd < peer_dd * 0.8:
            drawdown_score = 9
        elif max_dd < peer_dd * 1.1:
            drawdown_score = 7
        elif max_dd < peer_dd * 1.3:
            drawdown_score = 5
        else:
            drawdown_score = 3

        sharpe_1y = perf_1y.get("sharpe_ratio", 0) or 0
        sharpe_annual = sharpe_1y if sharpe_1y else sharpe_3y
        if sharpe_annual > 1.5:
            sharpe_score = 10
        elif sharpe_annual > 1.0:
            sharpe_score = 8
        elif sharpe_annual > 0.5:
            sharpe_score = 6
        elif sharpe_annual > 0.3:
            sharpe_score = 4
        else:
            sharpe_score = 2

        holders = fund.get("holders", None)
        if holders is not None and not (hasattr(holders, "empty") and holders.empty):
            inst_score = 5
        else:
            inst_score = 4

        micro_total = min(50, manager_score + alpha_score + drawdown_score + sharpe_score + inst_score)
        return micro_total, details, ""
