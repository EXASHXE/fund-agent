"""Structured intermediate schemas for the fund agent workflow."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FundFeature(BaseModel):
    code: str
    name: str = ""
    fund_type: str = ""
    data_completeness: str = ""
    score_seed: Optional[int] = None
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)
    exposure: Dict[str, Any] = Field(default_factory=dict)


class PortfolioSnapshot(BaseModel):
    snapshot_version: str = "portfolio_snapshot.v1"
    generated_at: datetime = Field(default_factory=datetime.now)
    report_date: Optional[str] = None
    holdings: List[Dict[str, Any]] = Field(default_factory=list)
    funds: List[FundFeature] = Field(default_factory=list)
    portfolio_metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class NewsEvent(BaseModel):
    event_id: str
    event_name: str
    event_type: str = "general"
    affected_assets: List[str] = Field(default_factory=list)
    direction: str = "neutral"
    sentiment_score: float = 0.5
    impact_score: float = 0.0
    confidence: float = 0.5
    first_seen: str = ""
    last_seen: str = ""
    decay_weight: float = 1.0
    source_count: int = 0
    sample_titles: List[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    code: str
    name: str
    score: float = 0.0
    theme: str = "其他"
    exposure_cluster: str = "balanced_other"
    portfolio_role: str = "待 agent 判断"
    marginal_benefit: float = 0.0
    diversification_score: float = 0.0
    reason: str = ""
    risks: List[str] = Field(default_factory=list)


class ReportContext(BaseModel):
    context_version: str = "report_context.v1"
    portfolio_snapshot: PortfolioSnapshot
    news_events: List[NewsEvent] = Field(default_factory=list)
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    agent_tasks: List[Dict[str, Any]] = Field(default_factory=list)
