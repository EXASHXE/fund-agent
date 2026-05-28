"""Meso scoring (weight: 30/100). Sector prosperity + valuation + policy + rotation."""
from typing import Dict, Optional, Tuple


class MesoScorer:
    def score(self, code: str, fund_data: dict, completeness: str) -> Tuple[Optional[int], Dict, str]:
        if completeness in ("C", "D"):
            return None, {}, ""

        fund = fund_data
        ft = fund.get("basic", {})
        fund_name = ft.get("name", "") if ft else ""
        fund_type = ft.get("fund_type", "domestic") if ft else "domestic"

        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name or "科技" in fund_name:
                prosperity, pe_score, policy, rotation = 4, 2, 4, 3
            elif "新兴市场" in fund_name:
                prosperity, pe_score, policy, rotation = 7, 6, 5, 5
            else:
                prosperity, pe_score, policy, rotation = 5, 4, 3, 3
        elif "石油" in fund_name or "能源" in fund_name:
            prosperity, pe_score, policy, rotation = 3, 3, 2, 2
        elif "新能源" in fund_name or "电池" in fund_name:
            prosperity, pe_score, policy, rotation = 3, 6, 4, 3
        elif "混合" in fund_type or "灵活" in fund_type:
            prosperity, pe_score, policy, rotation = 5, 5, 5, 4
        else:
            prosperity, pe_score, policy, rotation = 5, 4, 3, 3

        meso_total = min(30, prosperity + pe_score + policy + rotation)
        return meso_total, {}, ""
