"""Portfolio-level risk exposure matrix."""
from typing import Dict, List

import pandas as pd

from src.recommend.engine import infer_exposure_cluster


def build_portfolio_risk_matrix(
    holdings_data: Dict,
    scores: List[Dict],
    correlations: pd.DataFrame = None,
) -> Dict:
    """Build cluster exposure, high-correlation warnings and marginal risk."""
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
        cluster = infer_exposure_cluster(profile)
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
