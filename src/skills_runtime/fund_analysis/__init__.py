"""Fund analysis runtime package."""

from __future__ import annotations

from .evidence_stage import MAX_POSITION_EVIDENCE
from .optional_data_stage import (
    summarize_benchmark_gap,
    summarize_factor_exposures,
    summarize_fee_schedule,
    summarize_manager_profiles,
    summarize_peer_data,
    summarize_redemption_constraints,
)
from .skill import FundAnalysisSkill

__all__ = [
    "FundAnalysisSkill",
    "MAX_POSITION_EVIDENCE",
    "summarize_benchmark_gap",
    "summarize_factor_exposures",
    "summarize_fee_schedule",
    "summarize_manager_profiles",
    "summarize_peer_data",
    "summarize_redemption_constraints",
]
