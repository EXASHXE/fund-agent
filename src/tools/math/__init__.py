"""Math tools: XIRR, HHI, NAV matching, portfolio aggregation.

All functions in this package are PURE — they have zero IO, zero network,
zero LLM calls. They operate only on their input arguments.
"""

from src.tools.math.calc import (
    calc_xirr,
    compute_hhi,
    _parse_weight_pct,
    _find_closest_nav,
    _match_nav,
    _calc_xirr,
    compute_portfolio,
)
from src.tools.math.xirr import xirr

__all__ = [
    "xirr",
    "calc_xirr",
    "compute_hhi",
    "_parse_weight_pct",
    "_find_closest_nav",
    "_match_nav",
    "_calc_xirr",
    "compute_portfolio",
]
