"""新闻情绪与净值变化的相关性分析"""
from typing import List, Dict, Tuple
from datetime import date, timedelta


def news_nav_correlation(
    sentiment_daily: List[Dict],
    nav_daily_returns: List[Tuple[date, float]],
    lag_days: List[int] = None,
) -> Dict[int, Tuple[float, float]]:
    """计算新闻情绪与净值日收益率在不同滞后窗口下的 Spearman 相关。"""
    if lag_days is None:
        lag_days = [0, 1, 3, 5]

    try:
        from scipy.stats import spearmanr
    except ImportError:
        return {lag: (0.0, 1.0) for lag in lag_days}

    sent_map = {item["date"]: item["sentiment_mean"] for item in sentiment_daily}

    results = {}
    for lag in lag_days:
        pairs = []
        for nav_date, nav_return in nav_daily_returns:
            sent_date_str = (nav_date - timedelta(days=lag)).isoformat()
            if sent_date_str in sent_map:
                pairs.append((sent_map[sent_date_str], nav_return))

        if len(pairs) >= 5:
            r, p = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
            results[lag] = (round(r, 4), round(p, 4))
        else:
            results[lag] = (0.0, 1.0)

    return results
