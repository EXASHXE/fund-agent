"""Runtime facade -- stable public import path.

Exposes runtime bridge helpers for fund_analysis and decision_support.
Does NOT expose unstable internals.
"""
from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.decision_support import DecisionSupportSkill

__all__ = [
    "DecisionSupportSkill",
    "FundAnalysisSkill",
    "SkillInput",
    "SkillOutput",
]
