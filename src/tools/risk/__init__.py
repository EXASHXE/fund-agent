"""Risk analysis tools: metrics, correlations, stress testing.

All functions in this package are PURE — they have zero IO, zero network,
zero LLM calls. They operate only on their input arguments.
"""

from src.tools.risk.metrics import (
    sortino_ratio,
    compute_perf_from_nav,
    compute_correlations,
    stress_test,
    _fund_exposure_text,
    _infer_risk_scenarios,
)

__all__ = [
    "sortino_ratio",
    "compute_perf_from_nav",
    "compute_correlations",
    "stress_test",
    "_fund_exposure_text",
    "_infer_risk_scenarios",
]
