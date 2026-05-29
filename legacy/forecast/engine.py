"""Fund trend forecast engine."""
from typing import Dict


def build_trend_matrix(score: Dict, news_context: Dict = None) -> Dict:
    """Build short- and mid-term trend scores from score and news evidence."""
    news_context = news_context or {}
    feature = score.get("feature_matrix") or {}
    brief = news_context.get("brief") or {}
    news_eval = news_context.get("news_evaluation") or {}

    catalyst = _normalize_signed(float(brief.get("weighted_catalyst_score", 0) or 0), scale=0.5)
    score_delta_signal = _normalize_signed(float(score.get("score_delta") or 0), scale=20.0)
    risk_signal = _risk_signal(feature)
    baseline_signal = _normalize_signed(float(score.get("composite_score", 50) or 50) - 50, scale=50.0)

    short_score = _clip01(
        0.50
        + 0.22 * catalyst
        + 0.16 * score_delta_signal
        + 0.14 * risk_signal
        + 0.10 * baseline_signal
    )
    mid_score = _clip01(
        0.50
        + 0.14 * catalyst
        + 0.10 * score_delta_signal
        + 0.18 * risk_signal
        + 0.16 * baseline_signal
    )

    base_conf = {
        "A": 0.88,
        "B": 0.76,
        "C": 0.58,
        "D": 0.25,
    }.get(score.get("data_completeness"), 0.65)
    news_quality = float(news_eval.get("quality_score", 0.5) or 0.5)
    short_conf = _clip01(base_conf * 0.75 + news_quality * 0.25)
    mid_conf = _clip01(base_conf * 0.85 + news_quality * 0.15)

    return {
        "short_term": {
            "direction": _direction(short_score),
            "score": round(short_score, 4),
            "confidence": round(short_conf, 4),
            "horizon_days": 10,
        },
        "mid_term": {
            "direction": _direction(mid_score),
            "score": round(mid_score, 4),
            "confidence": round(mid_conf, 4),
            "horizon_days": 60,
        },
        "drivers": _drivers(catalyst, score_delta_signal, risk_signal, baseline_signal, brief),
    }


def _risk_signal(feature: Dict) -> float:
    sortino = feature.get("sortino_ratio")
    sharpe = feature.get("sharpe_1y")
    max_dd = feature.get("max_drawdown_3y_pct")
    signal = 0.0
    if sortino is not None:
        signal += _normalize_signed(float(sortino), scale=2.0) * 0.5
    if sharpe is not None:
        signal += _normalize_signed(float(sharpe), scale=2.0) * 0.3
    if max_dd is not None:
        signal -= _clip(float(max_dd) / 50.0, 0.0, 1.0) * 0.2
    return _clip(signal, -1.0, 1.0)


def _drivers(catalyst, score_delta_signal, risk_signal, baseline_signal, brief):
    drivers = []
    if catalyst > 0.1:
        drivers.append("新闻催化偏正")
    elif catalyst < -0.1:
        drivers.append("新闻催化偏负")
    if score_delta_signal > 0.1:
        drivers.append("评分趋势改善")
    elif score_delta_signal < -0.1:
        drivers.append("评分趋势走弱")
    if risk_signal > 0.1:
        drivers.append("风险收益指标较稳")
    elif risk_signal < -0.1:
        drivers.append("下行风险约束")
    if baseline_signal > 0.15:
        drivers.append("量化基准分较高")
    if brief.get("trend") in ("bullish", "bearish"):
        drivers.append(f"新闻简报趋势: {brief.get('trend')}")
    return drivers or ["趋势信号中性"]


def _direction(score: float) -> str:
    if score >= 0.65:
        return "up"
    if score < 0.45:
        return "down"
    return "flat"


def _normalize_signed(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clip(value / scale, -1.0, 1.0)


def _clip01(value: float) -> float:
    return _clip(value, 0.0, 1.0)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
