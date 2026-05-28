"""Tests for TavilySearchClient — AI-optimized search client for supplementary research."""
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock


class TavilySearchClientTest(unittest.TestCase):
    """Tests for TavilySearchClient initialization, graceful degradation, and normalization."""

    def test_init_without_api_key_does_not_crash(self):
        """Client should initialize without an API key and not crash."""
        from src.news.tavily_client import TavilySearchClient
        client = TavilySearchClient()
        self.assertIsNotNone(client)
        self.assertEqual(client.api_key, "")

    def test_init_with_explicit_api_key(self):
        """Client should accept an explicit API key."""
        from src.news.tavily_client import TavilySearchClient
        client = TavilySearchClient(api_key="tavily_test_key")
        self.assertEqual(client.api_key, "tavily_test_key")

    def test_init_with_env_var(self):
        """Client should read API key from environment variable TAVILY_API_KEY."""
        from src.news.tavily_client import TavilySearchClient
        with patch.dict(os.environ, {"TAVILY_API_KEY": "env_tavily_key"}):
            client = TavilySearchClient()
            self.assertEqual(client.api_key, "env_tavily_key")

    def test_get_client_returns_none_when_no_api_key(self):
        """_get_client should return None when api_key is empty."""
        from src.news.tavily_client import TavilySearchClient
        client = TavilySearchClient()
        result = client._get_client()
        self.assertIsNone(result)

    def test_search_finance_returns_empty_when_no_api_key(self):
        """search_finance should return empty list when API key is missing."""
        from src.news.tavily_client import TavilySearchClient
        client = TavilySearchClient()
        result = client.search_finance("AAPL earnings")
        self.assertEqual(result, [])

    def test_search_news_returns_empty_when_no_api_key(self):
        """search_news should return empty list when API key is missing."""
        from src.news.tavily_client import TavilySearchClient
        client = TavilySearchClient()
        result = client.search_news("Tesla stock")
        self.assertEqual(result, [])

    def test_normalize_converts_tavily_response_format(self):
        """_normalize should convert Tavily response to standard dict format."""
        from src.news.tavily_client import TavilySearchClient
        sample = [
            {
                "title": "Apple Reports Record Q2 Earnings",
                "content": "Apple Inc. beats Wall Street expectations.",
                "published_date": "2026-05-20",
                "url": "https://example.com/apple-q2",
                "score": 0.95,
                "raw_content": None,
            },
            {
                "title": "Tesla Deliveries Surge",
                "content": "Tesla exceeded delivery estimates.",
                "url": "https://example.com/tesla",
            },
        ]
        result = TavilySearchClient._normalize(sample)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Apple Reports Record Q2 Earnings")
        self.assertEqual(result[0]["content"], "Apple Inc. beats Wall Street expectations.")
        self.assertEqual(result[0]["date"], "2026-05-20")
        self.assertEqual(result[0]["source"], "Tavily")
        self.assertEqual(result[0]["url"], "https://example.com/apple-q2")
        self.assertEqual(result[0]["score"], 0.95)

    def test_normalize_handles_missing_fields(self):
        """_normalize should handle records with missing fields gracefully."""
        from src.news.tavily_client import TavilySearchClient
        sample = [{}]  # Empty record
        result = TavilySearchClient._normalize(sample)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "")
        self.assertEqual(result[0]["content"], "")
        self.assertEqual(result[0]["date"], "")
        self.assertEqual(result[0]["source"], "Tavily")
        self.assertEqual(result[0]["url"], "")
        self.assertEqual(result[0]["score"], 0)

    def test_normalize_empty_list(self):
        """_normalize should return empty list for empty input."""
        from src.news.tavily_client import TavilySearchClient
        result = TavilySearchClient._normalize([])
        self.assertEqual(result, [])

    def test_search_finance_with_mocked_client(self):
        """search_finance should call TavilyClient and return normalized results."""
        from src.news.tavily_client import TavilySearchClient
        fake_tavily = types.SimpleNamespace()
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "NVIDIA Earnings Beat",
                    "content": "NVIDIA reported strong Q1 earnings.",
                    "published_date": "2026-05-25",
                    "url": "https://example.com/nvda",
                    "score": 0.92,
                },
            ],
        }
        fake_tavily.TavilyClient = MagicMock(return_value=mock_client)

        old = sys.modules.get("tavily")
        sys.modules["tavily"] = fake_tavily
        try:
            client = TavilySearchClient(api_key="mock_key")
            result = client.search_finance("NVIDIA earnings")
        finally:
            if old is not None:
                sys.modules["tavily"] = old
            else:
                sys.modules.pop("tavily", None)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "NVIDIA Earnings Beat")
        self.assertEqual(result[0]["score"], 0.92)
        fake_tavily.TavilyClient.assert_called_once_with(api_key="mock_key")

    def test_search_finance_handles_exception(self):
        """search_finance should return empty list when API call raises exception."""
        from src.news.tavily_client import TavilySearchClient
        fake_tavily = types.SimpleNamespace()
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API error")
        fake_tavily.TavilyClient = MagicMock(return_value=mock_client)

        old = sys.modules.get("tavily")
        sys.modules["tavily"] = fake_tavily
        try:
            client = TavilySearchClient(api_key="mock_key")
            result = client.search_finance("AAPL")
        finally:
            if old is not None:
                sys.modules["tavily"] = old
            else:
                sys.modules.pop("tavily", None)

        self.assertEqual(result, [])

    def test_search_news_with_mocked_client(self):
        """search_news should call TavilyClient with news topic and days parameter."""
        from src.news.tavily_client import TavilySearchClient
        fake_tavily = types.SimpleNamespace()
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Federal Reserve Rate Decision",
                    "content": "Fed holds rates steady.",
                    "published_date": "2026-05-26",
                    "url": "https://example.com/fed",
                    "score": 0.88,
                },
            ],
        }
        fake_tavily.TavilyClient = MagicMock(return_value=mock_client)

        old = sys.modules.get("tavily")
        sys.modules["tavily"] = fake_tavily
        try:
            client = TavilySearchClient(api_key="mock_key")
            result = client.search_news("Federal Reserve", days=7, max_results=3)
        finally:
            if old is not None:
                sys.modules["tavily"] = old
            else:
                sys.modules.pop("tavily", None)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Federal Reserve Rate Decision")
        mock_client.search.assert_called_once_with(
            query="Federal Reserve",
            topic="news",
            search_depth="basic",
            max_results=3,
            days=7,
        )

    def test_search_news_handles_exception(self):
        """search_news should return empty list when API call raises exception."""
        from src.news.tavily_client import TavilySearchClient
        fake_tavily = types.SimpleNamespace()
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API error")
        fake_tavily.TavilyClient = MagicMock(return_value=mock_client)

        old = sys.modules.get("tavily")
        sys.modules["tavily"] = fake_tavily
        try:
            client = TavilySearchClient(api_key="mock_key")
            result = client.search_news("Test query")
        finally:
            if old is not None:
                sys.modules["tavily"] = old
            else:
                sys.modules.pop("tavily", None)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
