"""Sentiment Analysis Skill — polarity, intensity, confidence for symbols.

Uses ToolRegistry for tool access. No direct network calls.
All sentiment logic is lexicon-based with time decay and source weighting.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.schemas import EvidenceItem


@dataclass
class SentimentInput:
    """Typed input for sentiment analysis.

    Attributes:
        news_items: List of news dicts, each containing at minimum:
            - title (str): News title
            - description (str, optional): News description
            - symbols (list[str]): Related stock symbols
            - date/published_at (str): ISO date string
            - source (str): Source name
        symbols: List of symbols to compute aggregate sentiment for.
    """
    news_items: list[dict]
    symbols: list[str]


@dataclass
class SentimentOutput:
    """Typed output from sentiment analysis.

    Attributes:
        per_symbol: Dict mapping symbol -> {
            "polarity": float in [-1, 1] (negative to positive),
            "intensity": float in [0, 1] (strength of sentiment),
            "confidence": float in [0, 1] (reliability of estimate),
            "article_count": int,
            "decayed_score": float (time-decayed weighted score)
        }
        aggregate: Dict with overall portfolio sentiment metrics.
    """
    per_symbol: dict[str, dict[str, float]]
    aggregate: dict[str, float]


# Chinese financial sentiment lexicon
_POSITIVE_WORDS: frozenset[str] = frozenset({
    "利好", "增长", "盈利", "突破", "创新", "升级", "扩张",
    "回升", "反弹", "复苏", "改善", "提振", "加速", "超预期",
    "增持", "买入", "推荐", "领先", "优势", "龙头", "稀缺",
    "景气", "旺盛", "高增长", "扭亏", "翻红", "走高",
    "bullish", "outperform", "upgrade", "positive", "growth",
    "profit", "breakthrough", "innovation", "exceed",
})

_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "利空", "下跌", "亏损", "回落", "减持", "卖出", "预警",
    "风险", "危机", "处罚", "调查", "违规", "诉讼", "违约",
    "降级", "下调", "疲软", "萎缩", "衰退", "低迷", "滞涨",
    "暴雷", "崩盘", "恐慌", "抛售", "跌停", "跳水", "做空",
    "bearish", "underperform", "downgrade", "negative", "decline",
    "loss", "risk", "crisis", "investigation", "penalty",
})

_SOURCE_CONFIDENCE = {
    "finnhub": 0.85,
    "reuters": 0.90,
    "bloomberg": 0.90,
    "xinhua": 0.85,
    "tavily": 0.65,
    "akshare": 0.75,
    "default": 0.50,
}

_NEWS_HALF_LIFE_DAYS = 3.5  # Exponential decay half-life


class SentimentAnalysisSkill:
    """Multi-symbol sentiment analysis with time decay and source weighting.

    Pipeline:
        1. For each symbol, collect relevant news items.
        2. Compute polarity score via lexicon matching.
        3. Apply exponential time decay (half-life ~3.5 days).
        4. Weight by source confidence.
        5. Aggregate per-symbol and portfolio-level scores.

    Expected tools:
        - "sentiment.lexicon": get_lexicon(words) -> dict (optional override)
        - All tools optional; pure lexicon-based fallback always works.
    """

    def __init__(self, tool_registry: Any):
        self.tools = tool_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, input_data: SentimentInput) -> SentimentOutput:
        """Execute sentiment analysis for given symbols and news items.

        Returns per-symbol sentiment dict and aggregate portfolio metrics.
        """
        news_items = input_data.news_items
        symbols = input_data.symbols

        if not news_items or not symbols:
            empty_per_symbol: dict[str, dict[str, float]] = {
                sym: {
                    "polarity": 0.0,
                    "intensity": 0.0,
                    "confidence": 0.0,
                    "article_count": 0,
                    "decayed_score": 0.0,
                }
                for sym in symbols
            }
            return SentimentOutput(
                per_symbol=empty_per_symbol,
                aggregate={
                    "portfolio_polarity": 0.0,
                    "portfolio_intensity": 0.0,
                    "portfolio_confidence": 0.0,
                    "total_articles_analyzed": 0,
                    "positive_ratio": 0.0,
                    "negative_ratio": 0.0,
                    "neutral_ratio": 1.0,
                },
            )

        # ---- Step 1: Group news by symbol --------------------------------
        news_by_symbol: dict[str, list[dict]] = {sym: [] for sym in symbols}
        for item in news_items:
            item_symbols = item.get("symbols", item.get("related_symbols", []))
            if isinstance(item_symbols, str):
                item_symbols = [item_symbols]
            for sym in item_symbols:
                if sym in news_by_symbol:
                    news_by_symbol[sym].append(item)

        # ---- Step 2-4: Compute sentiment per symbol ----------------------
        now = datetime.now()
        per_symbol: dict[str, dict[str, float]] = {}

        for sym in symbols:
            items = news_by_symbol.get(sym, [])
            if not items:
                per_symbol[sym] = {
                    "polarity": 0.0,
                    "intensity": 0.0,
                    "confidence": 0.0,
                    "article_count": 0,
                    "decayed_score": 0.0,
                }
                continue

            weighted_polarity_sum = 0.0
            total_weight = 0.0
            total_confidence = 0.0
            total_raw_intensity = 0.0

            for item in items:
                # Polarity
                polarity = self._compute_polarity(item)

                # Time decay weight
                decay_weight = self._time_decay_weight(item, now)

                # Source confidence
                source_conf = self._source_confidence(item)

                # Intensity (absolute polarity)
                intensity = abs(polarity)

                # Composite weight
                weight = decay_weight * source_conf

                weighted_polarity_sum += polarity * weight
                total_weight += weight
                total_confidence += source_conf
                total_raw_intensity += intensity * weight

            article_count = len(items)
            avg_confidence = total_confidence / article_count if article_count > 0 else 0.0
            avg_polarity = (
                weighted_polarity_sum / total_weight if total_weight > 0 else 0.0
            )
            avg_intensity = (
                total_raw_intensity / total_weight if total_weight > 0 else 0.0
            )

            # Normalize polarity to [-1, 1], intensity to [0, 1]
            avg_polarity = max(-1.0, min(1.0, avg_polarity))
            avg_intensity = max(0.0, min(1.0, avg_intensity))

            # Decayed score = polarity * intensity (weighted by time)
            decayed_score = avg_polarity * avg_intensity

            per_symbol[sym] = {
                "polarity": round(avg_polarity, 4),
                "intensity": round(avg_intensity, 4),
                "confidence": round(avg_confidence, 4),
                "article_count": article_count,
                "decayed_score": round(decayed_score, 4),
            }

        # ---- Step 5: Aggregate portfolio sentiment -----------------------
        aggregate = self._compute_aggregate(per_symbol)

        return SentimentOutput(
            per_symbol=per_symbol,
            aggregate=aggregate,
        )

    # ------------------------------------------------------------------
    # Core sentiment computation (pure, no tool calls)
    # ------------------------------------------------------------------

    def _compute_polarity(self, news_item: dict) -> float:
        """Compute polarity score for a single news item using lexicon.

        Returns float in [-1, 1]:
        - Positive if more positive words than negative words.
        - Negative if more negative words than positive words.
        - Neutral if equal or no matches.
        """
        text = (
            f"{news_item.get('title', '')} "
            f"{news_item.get('description', '')} "
            f"{news_item.get('summary', '')}"
        ).lower()

        # Try custom lexicon from tool first
        try:
            lexicon = self.tools.invoke("sentiment.lexicon", words=text.split())
            if isinstance(lexicon, dict):
                pos_words = [w for w in lexicon.get("positive", []) if w in text]
                neg_words = [w for w in lexicon.get("negative", []) if w in text]
                pos_count = len(pos_words)
                neg_count = len(neg_words)
                total = pos_count + neg_count
                if total == 0:
                    return 0.0
                return (pos_count - neg_count) / max(total, 1)
        except (KeyError, TypeError, ValueError):
            pass

        # Default lexicon-based analysis: use substring matching
        # (Chinese text does not separate words with spaces)
        pos_count = sum(1 for w in _POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in _NEGATIVE_WORDS if w in text)
        total = pos_count + neg_count

        if total == 0:
            return 0.0  # neutral

        # Scale: (pos - neg) / max(total, 1), then normalize to [-1, 1]
        raw = (pos_count - neg_count) / max(total, 1)
        # Scale by log(count) so more signals = stronger polarity
        scale = min(1.0, math.log(total + 1) / math.log(10))
        return raw * scale

    @staticmethod
    def _time_decay_weight(news_item: dict, now: datetime) -> float:
        """Compute exponential time decay weight.

        Half-life: _NEWS_HALF_LIFE_DAYS (~3.5 days).
        Newer news = higher weight.
        """
        date_str = news_item.get("date") or news_item.get("published_at", "")
        if not date_str:
            return 0.5  # neutral weight if no date

        try:
            if isinstance(date_str, str):
                # Handle multiple date formats
                for fmt in (
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                ):
                    try:
                        pub_date = datetime.strptime(date_str[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0.5
            elif isinstance(date_str, datetime):
                pub_date = date_str
            else:
                return 0.5

            days_elapsed = (now - pub_date).total_seconds() / 86400.0
            if days_elapsed < 0:
                return 1.0  # future dates = max weight
            decay = math.exp(-math.log(2) * days_elapsed / _NEWS_HALF_LIFE_DAYS)
            return max(0.05, min(1.0, decay))
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _source_confidence(news_item: dict) -> float:
        """Get confidence weight for a news source."""
        source = (news_item.get("source") or "default").lower()
        return _SOURCE_CONFIDENCE.get(source, _SOURCE_CONFIDENCE["default"])

    @staticmethod
    def _compute_aggregate(
        per_symbol: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        """Compute aggregate portfolio-level sentiment metrics."""
        active = {
            sym: data
            for sym, data in per_symbol.items()
            if data["article_count"] > 0
        }

        if not active:
            return {
                "portfolio_polarity": 0.0,
                "portfolio_intensity": 0.0,
                "portfolio_confidence": 0.0,
                "total_articles_analyzed": 0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
            }

        total_articles = sum(d["article_count"] for d in active.values())
        total_confidence = sum(
            d["confidence"] * d["article_count"] for d in active.values()
        )
        # Value-weighted polarity
        weighted_polarity = sum(
            d["polarity"] * d["article_count"] for d in active.values()
        )

        # Positive/negative/neutral counts
        positive = sum(
            1 for d in active.values() if d["polarity"] > 0.05
        )
        negative = sum(
            1 for d in active.values() if d["polarity"] < -0.05
        )
        neutral_symbols = len(active) - positive - negative

        avg_intensity = sum(
            d["intensity"] for d in active.values()
        ) / len(active)

        return {
            "portfolio_polarity": round(
                weighted_polarity / total_articles, 4
            ),
            "portfolio_intensity": round(avg_intensity, 4),
            "portfolio_confidence": round(
                total_confidence / total_articles, 4
            ),
            "total_articles_analyzed": total_articles,
            "positive_ratio": round(positive / len(active), 4),
            "negative_ratio": round(negative / len(active), 4),
            "neutral_ratio": round(neutral_symbols / len(active), 4),
        }
