"""News fetch and catalyst quality evaluation."""
from datetime import date, datetime
from typing import Dict, List


def filter_relevant_catalysts(catalyst_news: List[Dict], min_relevance: float = 0.2) -> List[Dict]:
    """Keep catalyst items that are directly relevant enough for scoring."""
    return [
        item for item in (catalyst_news or [])
        if float((item.get("catalyst") or {}).get("relevance", 0) or 0) >= min_relevance
    ]


def evaluate_news_result(news_item: Dict, as_of=None, min_relevance: float = 0.2) -> Dict:
    """Evaluate whether fetched news is fresh, relevant, and usable for scoring."""
    if as_of is None:
        as_of_date = date.today()
    elif isinstance(as_of, date):
        as_of_date = as_of
    else:
        as_of_date = datetime.strptime(str(as_of)[:10], "%Y-%m-%d").date()

    news_list = news_item.get("news_list") or []
    catalysts = news_item.get("catalyst_news") or []
    relevant = filter_relevant_catalysts(catalysts, min_relevance=min_relevance)

    source_count = len({
        str(item.get("source", "")).strip()
        for item in news_list
        if str(item.get("source", "")).strip()
    })
    freshness_score = _freshness_score(news_list, as_of_date)
    relevance_score = _relevance_score(catalysts)
    source_diversity = min(1.0, source_count / 3.0)
    sample_score = min(1.0, len(news_list) / 8.0)
    quality_score = round(
        freshness_score * 0.35
        + relevance_score * 0.35
        + source_diversity * 0.15
        + sample_score * 0.15,
        4,
    )

    high_impact_negative = [
        item for item in relevant
        if float((item.get("catalyst") or {}).get("weighted_score", 0) or 0) <= -0.3
    ]
    high_impact = [
        item for item in relevant
        if abs(float((item.get("catalyst") or {}).get("weighted_score", 0) or 0)) >= 0.3
    ]
    negative_density = (
        len(high_impact_negative) / len(high_impact)
        if high_impact else 0.0
    )

    relevant_scores = [
        float((item.get("catalyst") or {}).get("weighted_score", 0) or 0)
        for item in relevant
    ]
    overall_score = round(sum(relevant_scores) / len(relevant_scores), 4) if relevant_scores else 0.0

    warnings = []
    if not news_list:
        warnings.append("未获取到有效新闻样本")
    if relevant and negative_density >= 0.5:
        warnings.append("高影响新闻中负向事件占比较高")
    if quality_score < 0.35:
        warnings.append("新闻样本质量偏低，评分参考权重应降低")

    return {
        "quality_score": quality_score,
        "freshness_score": round(freshness_score, 4),
        "relevance_score": round(relevance_score, 4),
        "source_count": source_count,
        "news_count": len(news_list),
        "relevant_news_count": len(relevant),
        "high_impact_negative_count": len(high_impact_negative),
        "negative_density": round(negative_density, 4),
        "overall_score": overall_score,
        "warnings": warnings,
    }


def _freshness_score(news_list: List[Dict], as_of_date: date) -> float:
    dates = []
    for item in news_list:
        parsed = _parse_date(item.get("date") or item.get("publish_date"))
        if parsed:
            dates.append(parsed)
    if not dates:
        return 0.0
    latest_age = min(max((as_of_date - d).days, 0) for d in dates)
    if latest_age <= 1:
        return 1.0
    if latest_age <= 3:
        return 0.75
    if latest_age <= 7:
        return 0.45
    return 0.15


def _relevance_score(catalysts: List[Dict]) -> float:
    if not catalysts:
        return 0.0
    values = [
        float((item.get("catalyst") or {}).get("relevance", 0) or 0)
        for item in catalysts
    ]
    return max(0.0, min(1.0, sum(values) / len(values)))


def _parse_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw[:10] if "-" in fmt or "/" in fmt else raw[:8], fmt).date()
        except ValueError:
            continue
    return None
