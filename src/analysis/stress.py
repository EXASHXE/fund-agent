"""情景压力测试"""
from typing import Dict, List


def stress_test(funds_data: Dict) -> List[Dict]:
    """对持仓基金进行 4 类情景压力测试。"""
    scenarios = [
        {"id": "S1", "desc": "美股大幅回调 (纳斯达克 -15%)",
         "target_keywords": ["纳斯达克", "致远", "QDII"], "drawdown_est": -12.0},
        {"id": "S2", "desc": "人民币大幅升值 (USD/CNY -5%)",
         "target_keywords": ["QDII"], "drawdown_est": -4.0},
        {"id": "S3", "desc": "大宗商品暴跌 (WTI原油 -20%)",
         "target_keywords": ["石油", "能源"], "drawdown_est": -16.0},
        {"id": "S4", "desc": "A股系统性下跌 (沪深300 -10%)",
         "target_keywords": ["混合", "新能源", "电池"], "drawdown_est": -8.0},
    ]

    results = []
    for sc in scenarios:
        for code, fund in funds_data.items():
            name = fund["basic"].get("name", "")
            ftype = fund["basic"].get("fund_type", "")
            hit = any(kw in name or kw in ftype for kw in sc["target_keywords"])
            if hit:
                results.append({
                    "scenario_id": sc["id"],
                    "scenario_desc": sc["desc"],
                    "fund_code": code,
                    "fund_name": name,
                    "estimated_drawdown_pct": sc["drawdown_est"],
                })
    return results
