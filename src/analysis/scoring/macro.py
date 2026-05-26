"""Macro scoring (weight: 20/100). Cycle fit + liquidity + valuation."""
from typing import Dict, Tuple


class MacroScorer:
    def score(self, code: str, fund_data: dict) -> Tuple[int, Dict, str]:
        fund = fund_data
        ft = fund.get("basic", {})
        fund_type = ft.get("fund_type", "domestic") if ft else "domestic"
        fund_name = ft.get("name", "") if ft else ""

        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name or "科技" in fund_name:
                cycle_score = 3
            elif "新兴市场" in fund_name:
                cycle_score = 5
            else:
                cycle_score = 4
        elif "指数" in fund_type or "ETF" in fund_type:
            if "石油" in fund_name or "能源" in fund_name:
                cycle_score = 4
            elif "新能源" in fund_name or "电池" in fund_name:
                cycle_score = 3
            else:
                cycle_score = 4
        elif "混合" in fund_type or "灵活" in fund_type:
            cycle_score = 5
        else:
            cycle_score = 4

        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            liquidity_score = 5
        else:
            liquidity_score = 5

        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name:
                valuation_score = 2
            elif "新兴市场" in fund_name:
                valuation_score = 5
            else:
                valuation_score = 4
        elif "指数" in fund_type or "ETF" in fund_type:
            valuation_score = 4
        else:
            valuation_score = 5

        macro_total = min(20, cycle_score + liquidity_score + valuation_score)
        return macro_total, {}, ""
