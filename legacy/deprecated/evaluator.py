"""News fetch and catalyst quality evaluation."""
from datetime import date, datetime
from typing import Dict, List


def filter_relevant_catalysts(catalyst_news: list[Dict], min_relevance: float = 0.2) -> list[Dict]:
    """Keep catalyst items that are directly relevant enough for scoring."""
    return [
        item for item in (catalyst_news or [])
        if float((item.get("catalyst") or {}).get("relevance", 0) or 0) >= min_relevance
    ]


def evaluate_news_result(
    news_item: Dict,
    as_of=None,
    min_relevance: float = 0.2,
    entity_profile=None,
) -> Dict:
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
    coverage = _holding_coverage(news_list, entity_profile)

    warnings = []
    if not news_list:
        warnings.append("未获取到有效新闻样本")
    if relevant and negative_density >= 0.5:
        warnings.append("高影响新闻中负向事件占比较高")
    if quality_score < 0.35:
        warnings.append("新闻样本质量偏低，评分参考权重应降低")
    if coverage["coverage_warning"]:
        warnings.append(coverage["coverage_warning"])

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
        **coverage,
        "warnings": warnings,
    }


def _holding_coverage(news_list: list[Dict], entity_profile) -> Dict:
    """Return portfolio-holding coverage evidence for an agent decision."""
    holdings = getattr(entity_profile, "holdings", []) if entity_profile else []
    if not holdings:
        return {
            "holding_coverage_count": 0,
            "holding_coverage_pct": None,
            "covered_holdings": [],
            "coverage_warning": "未取得持仓穿透数据，新闻覆盖度不可验证",
        }

    import re
    # Import translations to match English stock names to Chinese news terms
    try:
        from legacy.news.news_fetcher import _GLOBAL_STOCK_TRANSLATIONS
    except ImportError:
        _GLOBAL_STOCK_TRANSLATIONS = {}

    covered = []
    total_weight = 0.0
    covered_weight = 0.0
    texts = [
        f"{item.get('title', '')} {item.get('content', '')} {' '.join(item.get('matched_terms', []))}".lower()
        for item in news_list
    ]
    for holding in holdings:
        name = str(holding.get("stock_name") or holding.get("股票名称") or "").strip()
        code = str(holding.get("stock_code") or holding.get("股票代码") or "").strip()
        weight_val = holding.get("weight")
        if weight_val is None:
            weight_val = holding.get("占净值比例", 0)
        weight = _parse_weight(weight_val)
        total_weight += weight

        if not name:
            continue

        # Generate match terms
        match_terms = [name.lower()]
        if code:
            match_terms.append(code.lower())
        
        # Remove corporate suffixes to get the core name
        norm_name = re.sub(r'\b(corp|inc|co|ltd|plc|ag|group|s\.a\.|class\s+[a-z]|adr)\b', '', name, flags=re.IGNORECASE)
        norm_name = norm_name.replace(".", "").replace(",", "").strip()
        if norm_name and norm_name.lower() not in match_terms:
            match_terms.append(norm_name.lower())

        # Match translation
        for eng_key, chi_val in _GLOBAL_STOCK_TRANSLATIONS.items():
            if eng_key.lower() in name.lower() or (code and eng_key.lower() == code.lower()):
                if chi_val.lower() not in match_terms:
                    match_terms.append(chi_val.lower())
                if eng_key.lower() not in match_terms:
                    match_terms.append(eng_key.lower())

        # Check if any match term is in the texts
        matched = False
        for term in match_terms:
            if any(term in text for text in texts):
                matched = True
                break

        if matched:
            covered.append(name)
            covered_weight += weight

    coverage_pct = covered_weight / total_weight if total_weight else (len(covered) / len(holdings) if holdings else 0.0)
    warning = ""
    if len(covered) < min(3, len(holdings)) or coverage_pct < 0.30:
        warning = "新闻覆盖偏窄，不能代表基金已披露重仓敞口"
    return {
        "holding_coverage_count": len(covered),
        "holding_coverage_pct": round(coverage_pct, 4),
        "covered_holdings": covered,
        "coverage_warning": warning,
    }


def _parse_weight(value) -> float:
    try:
        raw = str(value).strip()
        if raw.endswith("%"):
            return float(raw[:-1]) / 100.0
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _freshness_score(news_list: list[Dict], as_of_date: date) -> float:
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


def _relevance_score(catalysts: list[Dict]) -> float:
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
