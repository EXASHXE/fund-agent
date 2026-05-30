"""Minimal adapter-only skill runtime handlers for Research OS."""

from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
from src.skills_runtime.thesis_generation import ThesisGenerationSkill

__all__ = [
    "DecisionSupportSkill",
    "FundAnalysisSkill",
    "NewsResearchSkill",
    "SentimentAnalysisSkill",
    "ThesisGenerationSkill",
]
