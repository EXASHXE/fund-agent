"""新闻模块数据结构定义"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class EntityProfile:
    """基金持仓实体画像"""
    fund_code: str
    fund_name: str
    stock_codes: List[str] = field(default_factory=list)
    stock_names: List[str] = field(default_factory=list)
    holdings: List[Dict] = field(default_factory=list)
    sector_keywords: List[str] = field(default_factory=list)
    theme_keywords: List[str] = field(default_factory=list)
    updated_at: Optional[str] = None


@dataclass
class NewsItem:
    """统一新闻对象"""
    title: str
    content: str = ""
    source: str = ""
    publish_time: str = ""
    url: str = ""
    entity_hits: List[str] = field(default_factory=list)
    sector_hits: List[str] = field(default_factory=list)
    dedup_key: str = ""
    raw_score: float = 0.0


@dataclass
class EventResult:
    """事件蒸馏结果"""
    event_type: str = ""
    polarity: int = 0
    severity: float = 0.0
    impact: float = 0.0
    impact_scope: str = ""
    entity: str = ""
    theme: str = ""
    summary: str = ""


@dataclass
class CatalystScore:
    """单条新闻催化评分"""
    title: str
    severity: float = 0.0
    impact: float = 0.0
    relevance: float = 0.0
    decay_weight: float = 1.0
    weighted_score: float = 0.0
    event_type: str = ""
    entity: str = ""


@dataclass
class FundNewsBrief:
    """基金级新闻简报"""
    fund_code: str
    fund_name: str
    date: str = ""
    total_news: int = 0
    weighted_catalyst_score: float = 0.0
    trend: str = "neutral"
    top_events: List[Dict] = field(default_factory=list)
    sector_summary: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
