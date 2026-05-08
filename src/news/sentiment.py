"""SnowNLP 情绪分析 + jieba 关键词提取"""
from collections import Counter
from typing import List, Dict
import re


def analyze_sentiment(news_list: List[Dict]) -> List[Dict]:
    """对新闻列表逐条进行情绪分析。"""
    results = []
    for item in news_list:
        text = item.get("content", "") or item.get("title", "")
        score = 0.5
        label = "neutral"
        top_keywords = []

        try:
            from snownlp import SnowNLP
            s = SnowNLP(text)
            score = s.sentiments
        except Exception:
            pass

        try:
            import jieba.analyse
            clean = re.sub(r'[^\u4e00-\u9fff\w]', '', text)
            top_keywords = jieba.analyse.extract_tags(clean, topK=10)
        except Exception:
            pass

        if score > 0.6:
            label = "positive"
        elif score < 0.4:
            label = "negative"

        results.append({
            **item,
            "sentiment_score": round(score, 4),
            "sentiment_label": label,
            "keywords": top_keywords,
        })

    return results


def daily_sentiment_aggregate(news_with_sentiment: List[Dict]) -> List[Dict]:
    """按日聚合情绪指标。"""
    by_date: Dict[str, List] = {}
    for item in news_with_sentiment:
        d = item.get("date", "")
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(item)

    results = []
    for d in sorted(by_date.keys()):
        items = by_date[d]
        n = len(items)
        scores = [it["sentiment_score"] for it in items]
        pos = sum(1 for it in items if it["sentiment_label"] == "positive")
        neg = sum(1 for it in items if it["sentiment_label"] == "negative")

        all_kw = []
        for it in items:
            all_kw.extend(it.get("keywords", []))
        top_kw = [w for w, _ in Counter(all_kw).most_common(10)]

        results.append({
            "date": d,
            "positive_rate": round(pos / n, 3) if n else 0,
            "negative_rate": round(neg / n, 3) if n else 0,
            "neutral_rate": round((n - pos - neg) / n, 3) if n else 0,
            "sentiment_mean": round(sum(scores) / n, 4) if n else 0.5,
            "news_count": n,
            "top_keywords": top_kw,
        })

    return results


def extract_sector_keywords(news_list: List[Dict]) -> List[str]:
    """从新闻列表中提取行业相关关键词。"""
    sector_patterns = [
        "半导体", "芯片", "人工智能", "AI", "新能源", "光伏", "锂电", "电池",
        "医药", "医疗", "消费", "白酒", "金融", "银行", "证券", "保险",
        "地产", "房地产", "汽车", "军工", "电力", "煤炭", "石油", "钢铁",
        "通信", "5G", "互联网", "软件", "传媒", "游戏",
    ]

    all_text = " ".join(
        (item.get("title", "") + " " + item.get("content", ""))
        for item in news_list
    )

    found = []
    for sector in sector_patterns:
        if sector in all_text:
            found.append(sector)

    return found
