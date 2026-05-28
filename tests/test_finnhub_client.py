"""Tests for FinnhubNewsClient — US stock news API client."""
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock


class FinnhubNewsClientTest(unittest.TestCase):
    """Tests for FinnhubNewsClient initialization, graceful degradation, and normalization."""

    def test_init_without_api_key_does_not_crash(self):
        """Client should initialize without an API key and not crash."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        self.assertIsNotNone(client)
        self.assertEqual(client.api_key, "")

    def test_init_with_explicit_api_key(self):
        """Client should accept an explicit API key."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient(api_key="test_key_123")
        self.assertEqual(client.api_key, "test_key_123")

    def test_init_with_env_var(self):
        """Client should read API key from environment variable FINNHUB_API_KEY."""
        from src.news.finnhub_client import FinnhubNewsClient
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "env_key_456"}):
            client = FinnhubNewsClient()
            self.assertEqual(client.api_key, "env_key_456")

    def test_init_with_empty_env_var(self):
        """Client should default to empty string when env var is empty."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient(api_key="")
        self.assertEqual(client.api_key, "")

    def test_get_client_returns_none_when_no_api_key(self):
        """_get_client should return None when api_key is empty."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        result = client._get_client()
        self.assertIsNone(result)

    def test_get_company_news_returns_empty_when_no_api_key(self):
        """get_company_news should return empty list when API key is missing."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        result = client.get_company_news("AAPL")
        self.assertEqual(result, [])

    def test_get_news_sentiment_returns_empty_when_no_api_key(self):
        """get_news_sentiment should return empty dict when API key is missing."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        result = client.get_news_sentiment("AAPL")
        self.assertEqual(result, {})

    def test_get_market_news_returns_empty_when_no_api_key(self):
        """get_market_news should return empty list when API key is missing."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        result = client.get_market_news()
        self.assertEqual(result, [])

    def test_search_news_returns_empty_when_no_api_key(self):
        """search_news should return empty list when API key is missing."""
        from src.news.finnhub_client import FinnhubNewsClient
        client = FinnhubNewsClient()
        result = client.search_news("AAPL")
        self.assertEqual(result, [])

    def test_normalize_converts_finnhub_response_format(self):
        """_normalize should convert Finnhub response to standard dict format."""
        from src.news.finnhub_client import FinnhubNewsClient
        sample = [{
            "headline": "Apple Reports Record Earnings",
            "summary": "Apple Inc. reported record quarterly earnings.",
            "datetime": 1720000000,
            "source": "Reuters",
            "url": "https://example.com/apple-earnings",
            "category": "company",
            "image": "",
            "id": 12345,
            "related": "",
        }]
        result = FinnhubNewsClient._normalize(sample, "AAPL")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Apple Reports Record Earnings")
        self.assertEqual(result[0]["content"], "Apple Inc. reported record quarterly earnings.")
        self.assertEqual(result[0]["source"], "Reuters")
        self.assertEqual(result[0]["url"], "https://example.com/apple-earnings")
        self.assertEqual(result[0]["symbol"], "AAPL")

    def test_normalize_handles_empty_datetime(self):
        """_normalize should handle items with missing datetime (timestamp 0)."""
        from src.news.finnhub_client import FinnhubNewsClient
        sample = [{
            "headline": "Test Headline",
            "summary": "Test Content",
            "datetime": 0,
            "source": "TestSource",
            "url": "https://example.com/test",
        }]
        result = FinnhubNewsClient._normalize(sample, "TSLA")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Headline")
        self.assertEqual(result[0]["date"], "")  # timestamp 0 produces empty

    def test_normalize_handles_missing_fields(self):
        """_normalize should handle records with missing fields gracefully."""
        from src.news.finnhub_client import FinnhubNewsClient
        sample = [{}]  # Empty record
        result = FinnhubNewsClient._normalize(sample, "MSFT")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "")
        self.assertEqual(result[0]["content"], "")
        self.assertEqual(result[0]["source"], "Finnhub")

    def test_get_company_news_with_mocked_client(self):
        """get_company_news should call finnhub.Client and return normalized news."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.company_news.return_value = [{
            "headline": "Tesla Delivers Record Q2",
            "summary": "Tesla beat delivery estimates.",
            "datetime": 1720000000,
            "source": "Bloomberg",
            "url": "https://example.com/tesla",
        }]
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_company_news("TSLA", days=30)
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Tesla Delivers Record Q2")
        self.assertEqual(result[0]["symbol"], "TSLA")
        fake_finnhub.Client.assert_called_once_with(api_key="mock_key")
        mock_client_instance.company_news.assert_called_once()

    def test_get_company_news_handles_client_exception(self):
        """get_company_news should return empty list when API call raises exception."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.company_news.side_effect = Exception("API error")
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_company_news("AAPL")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(result, [])

    def test_get_news_sentiment_with_mocked_client(self):
        """get_news_sentiment should call finnhub.Client and return sentiment data."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.news_sentiment.return_value = {
            "buzz": {"articlesInLastWeek": 42},
            "sentiment": {"bullishPercent": 65.0},
        }
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_news_sentiment("AAPL")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(result["buzz"]["articlesInLastWeek"], 42)
        mock_client_instance.news_sentiment.assert_called_once_with("AAPL")

    def test_get_news_sentiment_handles_exception(self):
        """get_news_sentiment should return empty dict when API call raises exception."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.news_sentiment.side_effect = Exception("API error")
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_news_sentiment("AAPL")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(result, {})

    def test_get_market_news_with_mocked_client(self):
        """get_market_news should call finnhub.Client and return general news."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.general_news.return_value = [
            {"headline": "Market Update", "summary": "Markets rally."},
        ]
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_market_news(category="general")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(len(result), 1)
        mock_client_instance.general_news.assert_called_once_with("general", min_id=0)

    def test_get_market_news_handles_exception(self):
        """get_market_news should return empty list when API call raises exception."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.general_news.side_effect = Exception("API error")
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.get_market_news()
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(result, [])

    def test_search_news_filters_by_query_keyword(self):
        """search_news should filter results by keyword in title or content."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.company_news.return_value = [
            {
                "headline": "Apple Launches New iPhone",
                "summary": "New product announcement.",
                "datetime": 1720000000,
                "source": "Reuters",
                "url": "https://example.com/1",
            },
            {
                "headline": "Tesla Stock Rises",
                "summary": "EV maker surges.",
                "datetime": 1720000000,
                "source": "Bloomberg",
                "url": "https://example.com/2",
            },
        ]
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.search_news("AAPL", query="iPhone")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(len(result), 1)
        self.assertIn("iPhone", result[0]["title"])

    def test_search_news_no_filter_when_no_query(self):
        """search_news should return all news when query is None."""
        from src.news.finnhub_client import FinnhubNewsClient
        fake_finnhub = types.SimpleNamespace()
        mock_client_instance = MagicMock()
        mock_client_instance.company_news.return_value = [
            {
                "headline": "News 1",
                "summary": "Content 1",
                "datetime": 1720000000,
                "source": "S1",
                "url": "https://example.com/1",
            },
            {
                "headline": "News 2",
                "summary": "Content 2",
                "datetime": 1720000000,
                "source": "S2",
                "url": "https://example.com/2",
            },
        ]
        fake_finnhub.Client = MagicMock(return_value=mock_client_instance)

        old = sys.modules.get("finnhub")
        sys.modules["finnhub"] = fake_finnhub
        try:
            client = FinnhubNewsClient(api_key="mock_key")
            result = client.search_news("AAPL")
        finally:
            if old is not None:
                sys.modules["finnhub"] = old
            else:
                sys.modules.pop("finnhub", None)

        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
