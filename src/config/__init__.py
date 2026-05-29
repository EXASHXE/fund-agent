"""DEPRECATED — use src.infra.config instead."""
import warnings
warnings.warn(
    "src.config is deprecated, use src.infra.config instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config.schema import (
    PortfolioConfig, FundHolding, Purchase, DCAStrategy,
    StrategyParams, UserProfile, RiskTolerance, FundType,
    ScoringParams, StopProfitLossParams, RebalanceParams,
)
from src.infra.config.loader import load_portfolio_config, import_to_database, generate_sample_yaml
from src.infra.config.shared import today, now, report_cutoff_hour, to_date, fmt_date
from src.infra.config.defaults import DEFAULT_STRATEGY, DEFAULT_PROFILE, QUANT_CONFIG

__all__ = [
    "PortfolioConfig", "FundHolding", "Purchase", "DCAStrategy",
    "StrategyParams", "UserProfile",
    "load_portfolio_config", "import_to_database", "generate_sample_yaml",
    "today", "now", "report_cutoff_hour", "to_date", "fmt_date",
    "DEFAULT_STRATEGY", "DEFAULT_PROFILE", "QUANT_CONFIG",
]
