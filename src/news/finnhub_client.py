"""Finnhub US stock news API client.

Free tier: 60 API calls/minute, company news (1yr history),
news sentiment, general market news.
No Chinese stock support — US equities only.
"""
import os
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


class FinnhubNewsClient:
    """Finnhub US stock news API client.

    Free tier: 60 API calls/minute, company news (1yr history),
    news sentiment, general market news.
    No Chinese stock support — US equities only.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            import finnhub
            self._client = finnhub.Client(api_key=self.api_key)
        return self._client

    def get_company_news(self, symbol: str, days: int = 30) -> list[dict]:
        """Get company-specific news for a US stock symbol.

        Returns list of dicts with: title, summary, url, source,
        datetime (unix), category, image.
        """
        client = self._get_client()
        if not client:
            return []
        try:
            to_date = date.today().isoformat()
            from_date = (date.today() - timedelta(days=days)).isoformat()
            news = client.company_news(symbol, _from=from_date, to=to_date)
            return self._normalize(news, symbol)
        except Exception as e:
            logger.debug(f"Finnhub company_news failed for {symbol}: {e}")
            return []

    def get_news_sentiment(self, symbol: str) -> dict:
        """Get news sentiment for a US stock."""
        client = self._get_client()
        if not client:
            return {}
        try:
            return client.news_sentiment(symbol)
        except Exception as e:
            logger.debug(f"Finnhub news_sentiment failed for {symbol}: {e}")
            return {}

    def get_market_news(self, category: str = "general", min_id: int = 0) -> list[dict]:
        """Get general market news."""
        client = self._get_client()
        if not client:
            return []
        try:
            return client.general_news(category, min_id=min_id)
        except Exception as e:
            logger.debug(f"Finnhub general_news failed: {e}")
            return []

    def search_news(self, symbol: str, query: str | None = None, days: int = 30) -> list[dict]:
        """Convenience: get company news mapped to standard format with optional keyword filter."""
        news = self.get_company_news(symbol, days=days)
        if query:
            q = query.lower()
            news = [n for n in news if q in n.get("title", "").lower()
                    or q in n.get("content", "").lower()]
        return news

    @staticmethod
    def _normalize(news_items: list, symbol: str) -> list[dict]:
        """Normalize Finnhub response to standard news dict format."""
        result = []
        for item in news_items:
            dt = item.get("datetime", 0)
            date_str = datetime.fromtimestamp(dt).isoformat() if dt else ""
            result.append({
                "title": item.get("headline", ""),
                "content": item.get("summary", ""),
                "date": date_str[:10],
                "source": item.get("source", "Finnhub"),
                "url": item.get("url", ""),
                "symbol": symbol,
            })
        return result
