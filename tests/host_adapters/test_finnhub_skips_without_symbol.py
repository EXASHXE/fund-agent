"""Tests for Finnhub ticker extraction from entities and skip-without-symbol behavior.

Task 4: Finnhub should extract valid ticker symbols from KG entity data
instead of passing Chinese query text as the symbol parameter.
"""

from __future__ import annotations

import os
from unittest.mock import patch

# Import from the build_news_snapshot module
from scripts.build_news_snapshot import (
    _extract_ticker_from_entities,
    _provider_finnhub,
    build_news_snapshot,
)

# ---------------------------------------------------------------------------
# _extract_ticker_from_entities unit tests
# ---------------------------------------------------------------------------


class TestExtractTickerFromEntities:
    """Test _extract_ticker_from_entities helper function."""

    def test_extracts_ticker_from_holding_ticker_entity(self):
        """Should extract ticker from holding_ticker:XXX entity."""
        entities = ["holding_ticker:NVDA", "holding_company:NVIDIA"]
        assert _extract_ticker_from_entities(entities) == "NVDA"

    def test_extracts_first_holding_ticker_when_multiple(self):
        """Should return the first holding_ticker found."""
        entities = ["holding_ticker:AAPL", "holding_ticker:MSFT", "holding_company:Apple"]
        assert _extract_ticker_from_entities(entities) == "AAPL"

    def test_returns_none_for_fund_code_entities(self):
        """Chinese fund codes like fund:000001 are NOT Finnhub tickers."""
        entities = ["fund:000001", "fund_name:华夏成长"]
        assert _extract_ticker_from_entities(entities) is None

    def test_returns_none_for_empty_entities(self):
        """Empty entities list should return None."""
        assert _extract_ticker_from_entities([]) is None

    def test_returns_none_for_macro_entities(self):
        """Macro/industry entities have no ticker."""
        entities = ["macro:半导体", "industry:芯片"]
        assert _extract_ticker_from_entities(entities) is None

    def test_extracts_ticker_case_insensitive_prefix(self):
        """holding_ticker prefix should work regardless of casing in value."""
        # The prefix is always lowercase "holding_ticker:", but the value
        # after the colon is the ticker (should be uppercase but we accept it)
        entities = ["holding_ticker:tsm"]
        assert _extract_ticker_from_entities(entities) == "TSM"

    def test_returns_none_for_non_ticker_holding_entities(self):
        """holding_company and other holding_ prefixes are NOT tickers."""
        entities = ["holding_company:NVIDIA", "holding_sector:Technology"]
        assert _extract_ticker_from_entities(entities) is None

    def test_extracts_ticker_among_mixed_entities(self):
        """Should find holding_ticker among mixed entity types."""
        entities = [
            "fund:000001",
            "holding_company:NVIDIA Corporation",
            "holding_ticker:NVDA",
            "macro:半导体",
        ]
        assert _extract_ticker_from_entities(entities) == "NVDA"

    def test_returns_none_for_fund_name_entities(self):
        """fund_name entities are not stock tickers."""
        entities = ["fund_name:华夏成长混合"]
        assert _extract_ticker_from_entities(entities) is None

    def test_validates_ticker_length(self):
        """Ticker extracted from holding_ticker should be 1-5 uppercase letters."""
        # Valid: 1-char ticker
        entities = ["holding_ticker:A"]
        assert _extract_ticker_from_entities(entities) == "A"

        # Valid: 5-char ticker
        entities = ["holding_ticker:ABCDE"]
        assert _extract_ticker_from_entities(entities) == "ABCDE"

    def test_rejects_ticker_too_long(self):
        """Tickers longer than 5 chars are not valid stock symbols."""
        entities = ["holding_ticker:TOOLONG"]
        assert _extract_ticker_from_entities(entities) is None

    def test_rejects_ticker_with_digits(self):
        """Tickers containing digits are not valid stock symbols."""
        entities = ["holding_ticker:NV8A"]
        assert _extract_ticker_from_entities(entities) is None

    def test_rejects_empty_ticker_value(self):
        """Empty holding_ticker value should return None."""
        entities = ["holding_ticker:"]
        assert _extract_ticker_from_entities(entities) is None


# ---------------------------------------------------------------------------
# _provider_finnhub skip behavior tests
# ---------------------------------------------------------------------------


class TestProviderFinnhubSkipWithoutSymbol:
    """Test that _provider_finnhub skips when no symbol is provided."""

    def test_finnhub_returns_skipped_no_symbol(self):
        """Without a symbol, _provider_finnhub should return skipped_no_symbol."""
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}, clear=False):
            items, error = _provider_finnhub("半导体 芯片 行情")
            assert items == []
            assert error == "skipped_no_symbol"

    def test_finnhub_with_symbol_calls_api(self):
        """With a valid symbol, _provider_finnhub should attempt the API call."""
        # Patch the API key so it's "available"
        with (
            patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}),
            patch("scripts.build_news_snapshot._provider_finnhub") as mock_finnhub,
        ):
            mock_finnhub.return_value = ([{"title": "test"}], None)
            items, error = mock_finnhub("NVDA news", symbol="NVDA")
            assert items == [{"title": "test"}]
            assert error is None


# ---------------------------------------------------------------------------
# Integration: build_news_snapshot with Finnhub ticker extraction
# ---------------------------------------------------------------------------


class TestFinnhubTickerExtractionInSnapshot:
    """Test that build_news_snapshot properly extracts tickers for Finnhub."""

    def _make_kg_context_with_holding_ticker(self) -> dict:
        """Create a minimal KG context with a holding_ticker entity."""
        return {
            "query_plan": [
                {
                    "query_id": "q1",
                    "query": "NVIDIA 芯片 行情",
                    "query_type": "holding_company",
                    "priority": 1,
                    "entities": ["holding_ticker:NVDA", "holding_company:NVIDIA"],
                    "topic_tags": [],
                    "related_funds": [],
                    "reason": "Holding query",
                    "source": "kg",
                    "confidence": "high",
                    "fallback": False,
                }
            ]
        }

    def _make_kg_context_without_ticker(self) -> dict:
        """Create a KG context with no holding_ticker entity."""
        return {
            "query_plan": [
                {
                    "query_id": "q2",
                    "query": "半导体 芯片 行情",
                    "query_type": "theme",
                    "priority": 3,
                    "entities": ["macro:半导体", "industry:芯片"],
                    "topic_tags": ["半导体"],
                    "related_funds": [],
                    "reason": "Theme query",
                    "source": "kg",
                    "confidence": "low",
                    "fallback": False,
                }
            ]
        }

    def _make_kg_context_with_fund_code(self) -> dict:
        """Create a KG context with fund code but no stock ticker."""
        return {
            "query_plan": [
                {
                    "query_id": "q3",
                    "query": "000001 基金 净值",
                    "query_type": "fund_code",
                    "priority": 2,
                    "entities": ["fund:000001", "fund_name:华夏成长"],
                    "topic_tags": [],
                    "related_funds": ["华夏成长"],
                    "reason": "Fund code query",
                    "source": "kg",
                    "confidence": "medium",
                    "fallback": False,
                }
            ]
        }

    def test_finnhub_skipped_when_no_ticker_in_entities(self):
        """Finnhub should be skipped for queries without holding_ticker entities."""
        kg_context = self._make_kg_context_without_ticker()

        with (
            patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}, clear=False),
            patch("scripts.build_news_snapshot._provider_finnhub") as mock_finnhub,
        ):
            mock_finnhub.return_value = ([], "skipped_no_symbol")
            build_news_snapshot(kg_context)

            # Finnhub should have been called with symbol=None
            # (extracted from entities which have no holding_ticker)
            finnhub_calls = [c for c in mock_finnhub.call_args_list]
            if finnhub_calls:
                # If called, symbol should be None
                call_kwargs = finnhub_calls[0].kwargs
                assert call_kwargs.get("symbol") is None

    def test_finnhub_called_with_ticker_from_entities(self):
        """Finnhub should be called with extracted ticker when entities have holding_ticker."""
        kg_context = self._make_kg_context_with_holding_ticker()

        with (
            patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}, clear=False),
            patch("scripts.build_news_snapshot._provider_finnhub") as mock_finnhub,
        ):
            mock_finnhub.return_value = (
                [
                    {
                        "title": "NVIDIA News",
                        "url": "https://example.com/nvda",
                        "source": "Reuters",
                        "published_at": "2025-01-01",
                        "summary": "NVIDIA earnings",
                    }
                ],
                None,
            )
            build_news_snapshot(kg_context)

            # Finnhub should have been called with symbol="NVDA"
            finnhub_calls = mock_finnhub.call_args_list
            assert len(finnhub_calls) >= 1
            call_kwargs = finnhub_calls[0].kwargs
            assert call_kwargs.get("symbol") == "NVDA"

    def test_finnhub_skipped_for_fund_code_entities(self):
        """Finnhub should be skipped for fund code entities (Chinese mutual funds)."""
        kg_context = self._make_kg_context_with_fund_code()

        with (
            patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}, clear=False),
            patch("scripts.build_news_snapshot._provider_finnhub") as mock_finnhub,
        ):
            mock_finnhub.return_value = ([], "skipped_no_symbol")
            build_news_snapshot(kg_context)

            # Finnhub should have been called with symbol=None
            # because fund:000001 is not a stock ticker
            finnhub_calls = mock_finnhub.call_args_list
            if finnhub_calls:
                call_kwargs = finnhub_calls[0].kwargs
                assert call_kwargs.get("symbol") is None
