"""Test market regime detection: compute rolling volatility, detect regimes from NAV series and events."""
from src.analysis.scoring.regime import detect_regime, compute_rolling_volatility, has_trend, has_black_swan, count_high_magnitude_events
from src.analysis.scoring.types import MarketRegime


class TestComputeRollingVolatility:
    """Compute rolling realized volatility from NAV series."""

    def test_computes_annualized_volatility_from_daily_returns(self):
        """Flat NAV series should produce low volatility."""
        nav_series = [1.0] * 100  # flat
        vol = compute_rolling_volatility(nav_series, window=20)
        assert vol < 0.02

    def test_more_volatile_series_produces_higher_volatility(self):
        """A noisy NAV series produces higher measurable volatility."""
        import math
        nav_series = [1.0 + 0.02 * math.sin(i * 0.5) for i in range(100)]
        flat_series = [1.0] * 100
        vol_noisy = compute_rolling_volatility(nav_series, window=20)
        vol_flat = compute_rolling_volatility(flat_series, window=20)
        assert vol_noisy > vol_flat

    def test_default_window_is_20(self):
        """Default rolling window is 20 days."""
        nav_series = [1.0 + 0.01 * i for i in range(60)]
        vol = compute_rolling_volatility(nav_series)
        assert vol >= 0


class TestHasTrend:
    """Detect directional price trends in NAV series."""

    def test_increasing_series_has_trend(self):
        """A steadily increasing series should be detected as trending."""
        nav_series = [1.0 + 0.001 * i for i in range(100)]
        assert has_trend(nav_series, window=60) is True

    def test_random_walk_has_no_trend(self):
        """A random walk should not be detected as trending."""
        import random
        random.seed(42)
        nav = [1.0]
        for _ in range(99):
            nav.append(nav[-1] * (1 + random.uniform(-0.01, 0.01)))
        assert has_trend(nav, window=60) is False

    def test_short_series_has_no_trend(self):
        """Series shorter than min_data_points returns False."""
        nav_series = [1.0] * 10
        assert has_trend(nav_series) is False


class TestBlackSwanDetection:
    """Identify black swan events from event list."""

    def test_event_list_with_black_swan_returns_true(self):
        events = [
            {"type": "earnings_surprise", "polarity": 0.5, "magnitude": 0.5},
            {"type": "black_swan", "polarity": -0.9, "magnitude": 0.9},
        ]
        assert has_black_swan(events) is True

    def test_event_list_without_black_swan_returns_false(self):
        events = [
            {"type": "rate_change", "polarity": -0.3, "magnitude": 0.5},
            {"type": "fund_flow", "polarity": 0.3, "magnitude": 0.4},
        ]
        assert has_black_swan(events) is False

    def test_empty_events_returns_false(self):
        assert has_black_swan([]) is False


class TestCountHighMagnitudeEvents:
    """Count events exceeding magnitude threshold."""

    def test_counts_events_above_6_magnitude_last_7_days(self):
        events = [
            {"type": "earnings", "magnitude": 0.7, "date": "2026-05-25"},
            {"type": "policy", "magnitude": 0.3, "date": "2026-05-26"},
            {"type": "market", "magnitude": 0.8, "date": "2026-05-26"},
        ]
        count = count_high_magnitude_events(events, days=7, threshold=0.6)
        assert count == 2

    def test_returns_zero_for_empty_events(self):
        assert count_high_magnitude_events([], days=7) == 0

    def test_events_without_magnitude_field_count_as_zero(self):
        events = [
            {"type": "fund_flow", "date": "2026-05-25"},
        ]
        count = count_high_magnitude_events(events, days=7)
        assert count == 0


class TestDetectRegime:
    """Detect market regime from NAV and events."""

    def test_detects_normal_regime_with_low_volatility_and_no_events(self):
        nav_series = [1.0] * 120  # zero volatility
        events = []
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.NORMAL

    def test_detects_high_volatility_regime_with_spiky_nav(self):
        import math
        # Create high-volatility NAV series
        nav_series = [1.0 + 0.1 * math.sin(i * 1.5) for i in range(120)]
        events = []
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.HIGH_VOLATILITY

    def test_detects_high_volatility_with_many_high_magnitude_events(self):
        nav_series = [1.0 + 0.005 * i for i in range(120)]
        events = [
            {"type": "event", "magnitude": 0.7, "date": "2026-05-25"},
            {"type": "event", "magnitude": 0.8, "date": "2026-05-26"},
            {"type": "event", "magnitude": 0.9, "date": "2026-05-26"},
            {"type": "event", "magnitude": 0.7, "date": "2026-05-27"},
        ]
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.HIGH_VOLATILITY

    def test_detects_trending_regime_with_steadily_increasing_low_vol_nav(self):
        # Steady uptrend with low volatility
        nav_series = [1.0 + 0.0002 * i for i in range(120)]
        events = []
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.TRENDING

    def test_detects_crisis_regime_with_black_swan_or_high_event_density(self):
        nav_series = [1.0 + 0.005 * i for i in range(120)]
        events = [
            {"type": "black_swan", "polarity": -0.9, "magnitude": 0.95, "date": "2026-05-25"},
        ]
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.CRISIS

    def test_crisis_with_very_high_event_density(self):
        nav_series = [1.0] * 120
        events = [
            {"type": "event", "magnitude": 0.7, "date": "2026-05-25"} for _ in range(6)
        ]
        regime = detect_regime(nav_series, events, vol_window=20)
        assert regime == MarketRegime.CRISIS

    def test_default_when_no_nav_data(self):
        """Empty NAV series returns NORMAL."""
        regime = detect_regime([], [], vol_window=20)
        assert regime == MarketRegime.NORMAL
