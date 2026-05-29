"""DEPRECATED — use src.infra.data instead."""
import warnings
warnings.warn(
    "src.data is deprecated, use src.infra.data instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.data.fetcher import (
    fetch_fund_basic,
    fetch_fund_nav,
    fetch_fund_performance,
    fetch_fund_holdings,
    fetch_fund_sectors,
    fetch_holder_structure,
)
__all__ = [
    "fetch_fund_basic",
    "fetch_fund_nav",
    "fetch_fund_performance",
    "fetch_fund_holdings",
    "fetch_fund_sectors",
    "fetch_holder_structure",
]

