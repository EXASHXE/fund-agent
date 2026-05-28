"""Portfolio risk matrix and summary builders (pure dict aggregation)."""
from __future__ import annotations

import pandas as pd
from typing import Dict, List


def _infer_exposure_cluster(candidate: Dict) -> str:
    """Infer coarse exposure cluster from fund name/type/theme (pure keyword matching).

    Extracted from src.recommend.engine.infer_exposure_cluster.
    """
    text = f"{candidate.get('name', '')} {candidate.get('type', '')} {candidate.get('theme', '')}"
    if any(kw in text for kw in ["债", "固收", "货币", "短债"]):
        return "defensive_income"
    if any(kw in text for kw in ["红利", "价值", "银行", "低波", "股息"]):
        return "value_dividend"
    if any(kw in text for kw in ["QDII", "纳斯达克", "标普", "海外", "全球", "新兴市场"]):
        return "overseas"
    if any(kw in text for kw in ["医药", "医疗", "创新药", "生物"]):
        return "healthcare"
    if any(kw in text for kw in ["半导体", "芯片", "新能源", "电池", "光伏", "储能", "AI", "人工智能", "科技"]):
        return "growth_manufacturing"
    if any(kw in text for kw in ["黄金", "石油", "原油", "商品", "能源"]):
        return "commodity"
    if any(kw in text for kw in ["沪深300", "中证500", "中证1000", "上证50", "宽基"]):
        return "broad_beta"
    return "balanced_other"


def build_portfolio_risk_matrix(
    holdings_data: Dict,
    scores: List[Dict],
    correlations: pd.DataFrame = None,
) -> Dict:
    """Build cluster exposure, high-correlation warnings and marginal risk.

    Pure dict aggregation with no IO/network/LLM dependencies.
    pandas DataFrame is accepted for the optional correlations matrix.
    """
    holdings = (holdings_data or {}).get("funds") or []
    total_value = float((holdings_data or {}).get("total_value") or 0)
    score_by_code = {s.get("fund_code"): s for s in scores or []}

    cluster_exposures = {}
    fund_clusters = {}
    marginal_risk = {}

    for item in holdings:
        code = item.get("code")
        value = float(item.get("value") or item.get("current_value") or 0)
        weight = value / total_value if total_value else 0.0
        score = score_by_code.get(code, {})
        profile = {
            "code": code,
            "name": item.get("name") or score.get("fund_name", ""),
            "type": score.get("fund_type") or item.get("fund_type", ""),
            "theme": score.get("theme", ""),
        }
        cluster = _infer_exposure_cluster(profile)
        fund_clusters[code] = cluster
        cluster_exposures[cluster] = cluster_exposures.get(cluster, 0.0) + weight
        marginal_risk[code] = {
            "cluster": cluster,
            "position_weight": round(weight, 4),
            "correlation_load": 0.0,
            "risk_score": round(weight, 4),
        }

    warnings = []
    if correlations is not None and not correlations.empty:
        codes = [c for c in correlations.columns if c in marginal_risk]
        for code in codes:
            peers = [
                abs(float(correlations.loc[code, peer]))
                for peer in codes
                if peer != code and code in correlations.index and peer in correlations.columns
            ]
            corr_load = sum(peers) / len(peers) if peers else 0.0
            marginal_risk[code]["correlation_load"] = round(corr_load, 4)
            marginal_risk[code]["risk_score"] = round(
                marginal_risk[code]["position_weight"] * (1 + corr_load),
                4,
            )

        for i, left in enumerate(codes):
            for right in codes[i + 1:]:
                corr = float(correlations.loc[left, right])
                if abs(corr) > 0.85:
                    warnings.append(f"{left}-{right} 高相关，相关系数 {corr:.2f}，存在重复敞口")

    for cluster, exposure in sorted(cluster_exposures.items(), key=lambda x: x[1], reverse=True):
        if exposure > 0.50:
            warnings.append(f"{cluster} 暴露 {exposure:.0%}，超过组合集中度阈值")

    return {
        "cluster_exposures": {k: round(v, 4) for k, v in cluster_exposures.items()},
        "fund_clusters": fund_clusters,
        "marginal_risk": marginal_risk,
        "warnings": warnings,
    }


def portfolio_summary(holding_analyses: List[Dict]) -> Dict:
    """Aggregate per-fund holding analyses into a portfolio summary.

    Pure dict aggregation with no IO/network/LLM dependencies.
    """
    total_cost = sum(h["total_cost"] for h in holding_analyses)
    total_value = sum(h["current_value"] for h in holding_analyses)
    total_profit = total_value - total_cost
    total_pending = sum(h.get("pending_amount", 0) for h in holding_analyses)

    total_day_profit = sum(h.get("day_profit") or 0.0 for h in holding_analyses)
    prev_total_value = sum((h["current_value"] - (h.get("day_profit") or 0.0)) for h in holding_analyses)
    total_day_return_pct = round(total_day_profit / prev_total_value * 100, 2) if prev_total_value > 0 else 0.0

    funds = []
    for h in holding_analyses:
        dca_status = "启用中" if (h.get("dca_records") or h.get("dca_enabled")) else "未设置"
        funds.append({
            "code": h["fund_code"],
            "name": h["fund_name"],
            "value": h["current_value"],
            "cost": h["total_cost"],
            "profit": h["profit"],
            "return_pct": h["return_pct"],
            "week_profit": h.get("week_profit"),
            "week_return_pct": h.get("week_return_pct"),
            "day_profit": h.get("day_profit"),
            "day_return_pct": h.get("day_return_pct"),
            "annual_return": h["annual_return"],
            "avg_cost": h.get("avg_cost", 0),
            "pending_amount": h.get("pending_amount", 0),
            "dca_status": dca_status,
        })

    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_pending": round(total_pending, 2),
        "total_return_pct": round(total_profit / total_cost * 100, 2) if total_cost else 0,
        "total_day_profit": round(total_day_profit, 2),
        "total_day_return_pct": total_day_return_pct,
        "fund_count": len(holding_analyses),
        "funds": funds,
        "by_fund": {h["fund_code"]: h for h in holding_analyses},
    }
