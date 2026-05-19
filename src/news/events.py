"""News event extraction, clustering, and time-decay scoring."""
from collections import defaultdict
from datetime import datetime
from hashlib import md5
from math import exp, log
from typing import Dict, List

from src.analysis.schemas import NewsEvent
from src.config.shared import today as _shared_today


EVENT_PATTERNS = {
    "semiconductor": ["半导体", "芯片", "集成电路", "寒武纪", "精测电子", "国产替代"],
    "ai_compute": ["AI", "人工智能", "算力", "大模型", "服务器", "光模块"],
    "new_energy": ["新能源", "锂电", "电池", "光伏", "储能", "电动车"],
    "overseas": ["美股", "纳斯达克", "标普", "美元", "汇率", "海外"],
    "rates_credit": ["利率", "国债", "信用债", "央行", "降息", "加息"],
    "consumer_health": ["消费", "白酒", "医药", "医疗", "创新药", "集采"],
    "commodity": ["石油", "原油", "黄金", "煤炭", "商品"],
    "policy": ["政策", "监管", "补贴", "产业基金", "会议"],
    "earnings": ["业绩", "利润", "营收", "预增", "预减", "财报"],
    "capital_flow": ["资金流入", "净流入", "减持", "增持", "北向", "ETF"],
}

NEGATIVE_TERMS = ["下跌", "回落", "风险", "承压", "预减", "亏损", "减持", "监管", "制裁"]
POSITIVE_TERMS = ["上涨", "走强", "利好", "预增", "增持", "突破", "复苏", "净流入"]


def extract_news_events(news_with_sentiment: List[Dict], half_life_days: int = 7) -> List[Dict]:
    """Extract clustered event-level signals from raw news sentiment rows."""
    clusters = defaultdict(list)
    for item in news_with_sentiment or []:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        event_types = _match_event_types(text)
        if not event_types:
            event_types = ["general"]
        assets = _match_assets(text, event_types)
        cluster_key = "|".join(sorted(event_types[:2] + assets[:3]))
        clusters[cluster_key].append({**item, "_event_types": event_types, "_assets": assets})

    events = []
    for key, items in clusters.items():
        dates = [i.get("date", "") for i in items if i.get("date")]
        scores = [float(i.get("sentiment_score", 0.5) or 0.5) for i in items]
        latest_date = max(dates) if dates else ""
        decay = _decay_weight(latest_date, half_life_days)
        mean_sentiment = sum(scores) / len(scores) if scores else 0.5
        direction = _direction(items, mean_sentiment)
        event_types = _most_common([t for i in items for t in i.get("_event_types", [])])
        assets = _most_common([a for i in items for a in i.get("_assets", [])])
        impact = _impact_score(mean_sentiment, decay, len(items), direction)
        event_name = _event_name(event_types, assets)
        events.append(NewsEvent(
            event_id=md5(key.encode()).hexdigest()[:12],
            event_name=event_name,
            event_type=event_types[0] if event_types else "general",
            affected_assets=assets[:6],
            direction=direction,
            sentiment_score=round(mean_sentiment, 4),
            impact_score=round(impact, 4),
            confidence=round(min(0.95, 0.35 + 0.12 * len(items) + 0.15 * decay), 4),
            first_seen=min(dates) if dates else "",
            last_seen=latest_date,
            decay_weight=round(decay, 4),
            source_count=len(items),
            sample_titles=[i.get("title", "")[:100] for i in items[:3] if i.get("title")],
        ).model_dump())

    events.sort(key=lambda x: (x.get("impact_score", 0), x.get("last_seen", "")), reverse=True)
    return events


def _match_event_types(text: str) -> List[str]:
    return [name for name, kws in EVENT_PATTERNS.items() if any(kw in text for kw in kws)]


def _match_assets(text: str, event_types: List[str]) -> List[str]:
    assets = []
    for kws in EVENT_PATTERNS.values():
        for kw in kws:
            if kw in text and kw not in assets:
                assets.append(kw)
    for event_type in event_types:
        if event_type not in assets:
            assets.append(event_type)
    return assets


def _direction(items: List[Dict], mean_sentiment: float) -> str:
    text = " ".join(f"{i.get('title', '')} {i.get('content', '')}" for i in items)
    neg = sum(1 for term in NEGATIVE_TERMS if term in text)
    pos = sum(1 for term in POSITIVE_TERMS if term in text)
    if neg > pos or mean_sentiment < 0.42:
        return "negative"
    if pos > neg or mean_sentiment > 0.58:
        return "positive"
    return "neutral"


def _decay_weight(date_str: str, half_life_days: int) -> float:
    if not date_str:
        return 0.5
    try:
        d = datetime.fromisoformat(date_str[:10]).date()
    except ValueError:
        return 0.5
    age = max(0, (_shared_today() - d).days)
    return exp(-log(2) * age / max(1, half_life_days))


def _impact_score(sentiment: float, decay: float, source_count: int, direction: str) -> float:
    distance = abs(sentiment - 0.5) * 2
    sign = -1 if direction == "negative" else 1
    return sign * distance * decay * min(1.0, 0.45 + 0.18 * source_count)


def _most_common(values: List[str]) -> List[str]:
    counts = defaultdict(int)
    for value in values:
        if value:
            counts[value] += 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]


def _event_name(event_types: List[str], assets: List[str]) -> str:
    label = {
        "semiconductor": "半导体链事件",
        "ai_compute": "AI算力链事件",
        "new_energy": "新能源链事件",
        "overseas": "海外市场/汇率事件",
        "rates_credit": "利率信用事件",
        "consumer_health": "消费医药事件",
        "commodity": "商品价格事件",
        "policy": "政策事件",
        "earnings": "业绩事件",
        "capital_flow": "资金流事件",
        "general": "综合新闻事件",
    }.get(event_types[0] if event_types else "general", "综合新闻事件")
    if assets:
        return f"{label}：{', '.join(assets[:3])}"
    return label
