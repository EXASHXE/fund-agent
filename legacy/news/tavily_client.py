"""Tavily AI-optimized search client for supplementary research.

Free tier: 1,000 API calls/month. Rate limit: 100 RPM.
Use for ad-hoc research queries, not systematic news aggregation.
"""
import os
import logging

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """Tavily AI-optimized search client for supplementary research.

    Free tier: 1,000 API calls/month. Rate limit: 100 RPM.
    Use for ad-hoc research queries, not systematic news aggregation.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search_finance(self, query: str, max_results: int = 5) -> list[dict]:
        """Search for financial information on a specific topic/company."""
        client = self._get_client()
        if not client:
            return []
        try:
            response = client.search(
                query=query,
                topic="finance",
                search_depth="basic",
                max_results=max_results,
            )
            return self._normalize(response.get("results", []))
        except Exception as e:
            logger.debug(f"Tavily finance search failed: {e}")
            return []

    def search_news(self, query: str, days: int = 7, max_results: int = 5) -> list[dict]:
        """Search for recent news on a specific topic."""
        client = self._get_client()
        if not client:
            return []
        try:
            response = client.search(
                query=query,
                topic="news",
                search_depth="basic",
                max_results=max_results,
                days=days,
            )
            return self._normalize(response.get("results", []))
        except Exception as e:
            logger.debug(f"Tavily news search failed: {e}")
            return []

    @staticmethod
    def _normalize(results: list) -> list[dict]:
        """Normalize Tavily response to standard news dict format."""
        return [{
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "date": r.get("published_date", ""),
            "source": "Tavily",
            "url": r.get("url", ""),
            "score": r.get("score", 0),
        } for r in results]
