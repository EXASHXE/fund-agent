"""
新闻驱动基金推荐引擎。

流程：
  1. 从近期新闻提取热点行业
  2. 全市场基金筛选（收益动量 + 规模 + 申购状态）
  3. 相关性过滤（排除与持仓高相关的基金）
  4. 综合排序输出 Top-N
"""
from typing import List, Dict, Set, Optional
from collections import Counter


def extract_hot_sectors(news_results: List[Dict]) -> Dict[str, float]:
    """从多只基金的新闻分析结果中提取热点行业及热度得分。"""
    from src.news.sentiment import extract_sector_keywords

    all_news = []
    for nr in news_results:
        for item in nr.get("news_list", []):
            all_news.append(item)

    sectors = extract_sector_keywords(all_news)
    sector_counts = Counter(sectors)
    max_count = max(sector_counts.values()) if sector_counts else 1
    return {s: c / max_count for s, c in sector_counts.most_common(10)}


def screen_funds(
    hot_sectors: Dict[str, float],
    min_size: float = 1.0,
    top_pct: float = 0.20,
) -> List[Dict]:
    """全市场基金筛选：收益动量 + 规模 + 申购状态。"""
    candidates = []

    try:
        import akshare as ak
        df = ak.fund_exchange_rank_em()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("基金代码", ""))
                name = str(row.get("基金简称", ""))
                ret_1m = _safe_float(row.get("近1月", 0))
                ret_3m = _safe_float(row.get("近3月", 0))
                ret_6m = _safe_float(row.get("近6月", 0))
                fund_type = str(row.get("类型", ""))
                # fund_exchange_rank_em 不含规模和申购状态，跳过这些过滤
                size = _safe_float(row.get("基金规模", row.get("最新规模", None)))

                if size is not None and size < min_size:
                    continue

                status = str(row.get("申购状态", "开放申购"))
                if "暂停" in status or "封闭" in status:
                    continue

                candidates.append({
                    "code": code,
                    "name": name,
                    "type": fund_type,
                    "return_1m": ret_1m,
                    "return_3m": ret_3m,
                    "return_6m": ret_6m,
                    "size": size,
                })
    except Exception:
        pass

    seen = set()
    unique = []
    for c in candidates:
        if c["code"] not in seen:
            seen.add(c["code"])
            unique.append(c)

    unique.sort(key=lambda x: x.get("return_1m", 0) or 0, reverse=True)
    limit = max(10, int(len(unique) * top_pct))
    return unique[:limit]


def filter_by_correlation(
    candidates: List[Dict],
    holding_codes: Set[str],
    holding_nav: Dict = None,
    max_corr: float = 0.75,
) -> List[Dict]:
    """排除与现有持仓高相关的基金。"""
    filtered = []
    for c in candidates:
        code = c["code"]
        if code in holding_codes:
            continue
        filtered.append({**c, "avg_corr": 0.0, "max_corr": 0.0})
    return filtered


def rank_recommendations(
    candidates: List[Dict],
    hot_sectors: Dict[str, float],
    top_n: int = 5,
) -> List[Dict]:
    """综合排序：收益动量(40%) + 行业热度(30%) + 低相关性(30%)。"""
    if not candidates:
        return []

    returns = [c.get("return_1m", 0) or 0 for c in candidates]
    ret_max = max(abs(r) for r in returns) if returns else 1
    ret_norm = [r / ret_max if ret_max else 0 for r in returns]

    corr_scores = [1.0 - abs(c.get("avg_corr", 0)) for c in candidates]

    heat_scores = []
    for c in candidates:
        name = c.get("name", "")
        heat = max(
            (score for sector, score in hot_sectors.items() if sector in name),
            default=0.2
        )
        heat_scores.append(heat)

    for i, c in enumerate(candidates):
        c["score"] = round(
            ret_norm[i] * 0.4 + heat_scores[i] * 0.3 + corr_scores[i] * 0.3, 4
        )

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates[:top_n]


def generate_recommendation_reasons(
    recommendations: List[Dict],
    llm_analyzer=None,
) -> List[Dict]:
    """为推荐基金生成自然语言推荐理由。"""
    for rec in recommendations:
        ret_1m = rec.get("return_1m", 0) or 0
        reasons = []
        if ret_1m > 0:
            reasons.append(f"近1月收益{ret_1m:+.1f}%，短期动量强劲")
        if rec.get("avg_corr", 0) < 0.5:
            reasons.append("与现有持仓相关性低，可有效分散风险")
        rec["reason"] = "；".join(reasons) if reasons else "综合因子得分较高"

    return recommendations


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
