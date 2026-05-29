"""Event type hierarchy for news event extraction and classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class EventCategory(Enum):
    FUNDAMENTAL = "fundamental"
    POLICY = "policy"
    MARKET = "market"
    GEOPOLITICAL = "geopolitical"
    COMMODITY = "commodity"
    TECHNOLOGY = "technology"
    MACRO = "macro"


class EventType(Enum):
    # Fundamental events
    EARNINGS_SURPRISE = "earnings_surprise"
    EARNINGS_MISS = "earnings_miss"
    DIVIDEND_CHANGE = "dividend_change"
    MANAGEMENT_CHANGE = "management_change"
    MERGER_ACQUISITION = "merger_acquisition"
    # Policy events
    RATE_CHANGE = "rate_change"
    POLICY_SHIFT = "policy_shift"
    REGULATORY_ACTION = "regulatory_action"
    TRADE_RESTRICTION = "trade_restriction"
    SUBSIDY_CHANGE = "subsidy_change"
    # Market events
    FUND_FLOW = "fund_flow"
    INDEX_REBALANCE = "index_rebalance"
    MARKET_CRASH = "market_crash"
    SECTOR_ROTATION = "sector_rotation"
    # Geopolitical events
    GEOPOLITICAL = "geopolitical"
    SANCTIONS = "sanctions"
    WAR_CONFLICT = "war_conflict"
    # Commodity events
    COMMODITY_PRICE = "commodity_price"
    OIL_PRICE = "oil_price"
    GOLD_PRICE = "gold_price"
    # Technology events
    TECH_BREAKTHROUGH = "tech_breakthrough"
    INDUSTRY_CYCLE = "industry_cycle"
    SUPPLY_DISRUPTION = "supply_disruption"
    # Special
    BLACK_SWAN = "black_swan"
    OTHER = "other"


# Event hierarchy: category → list of event types
EVENT_HIERARCHY: dict[EventCategory, list[EventType]] = {
    EventCategory.FUNDAMENTAL: [
        EventType.EARNINGS_SURPRISE,
        EventType.EARNINGS_MISS,
        EventType.DIVIDEND_CHANGE,
        EventType.MANAGEMENT_CHANGE,
        EventType.MERGER_ACQUISITION,
    ],
    EventCategory.POLICY: [
        EventType.RATE_CHANGE,
        EventType.POLICY_SHIFT,
        EventType.REGULATORY_ACTION,
        EventType.TRADE_RESTRICTION,
        EventType.SUBSIDY_CHANGE,
    ],
    EventCategory.MARKET: [
        EventType.FUND_FLOW,
        EventType.INDEX_REBALANCE,
        EventType.MARKET_CRASH,
        EventType.SECTOR_ROTATION,
    ],
    EventCategory.GEOPOLITICAL: [
        EventType.GEOPOLITICAL,
        EventType.SANCTIONS,
        EventType.WAR_CONFLICT,
    ],
    EventCategory.COMMODITY: [
        EventType.COMMODITY_PRICE,
        EventType.OIL_PRICE,
        EventType.GOLD_PRICE,
    ],
    EventCategory.TECHNOLOGY: [
        EventType.TECH_BREAKTHROUGH,
        EventType.INDUSTRY_CYCLE,
        EventType.SUPPLY_DISRUPTION,
    ],
    EventCategory.MACRO: [
        EventType.BLACK_SWAN,
        EventType.OTHER,
    ],
}

# Keyword → EventType mapping for rule-based classification
EVENT_KEYWORDS: dict[EventType, list[str]] = {
    EventType.EARNINGS_SURPRISE: ["超预期", "业绩大增", "业绩超", "财报超", "盈利超"],
    EventType.EARNINGS_MISS: ["低于预期", "业绩下滑", "亏损", "商誉减值"],
    EventType.RATE_CHANGE: ["加息", "降息", "LPR", "利率", "美联储", "央行利率", "FOMC", "基准利率"],
    EventType.POLICY_SHIFT: ["政策", "监管", "备案", "审批", "产业政策", "指导", "规划"],
    EventType.REGULATORY_ACTION: ["处罚", "整改", "下架", "禁令", "反垄断", "审查"],
    EventType.TRADE_RESTRICTION: ["关税", "贸易壁垒", "出口限制", "芯片禁令", "制裁", "实体清单"],
    EventType.GEOPOLITICAL: ["地缘政治", "中美关系", "台海", "国际局势", "外交"],
    EventType.COMMODITY_PRICE: ["涨价", "跌价", "价格波动", "供需"],
    EventType.OIL_PRICE: ["原油", "油价", "OPEC", "石油"],
    EventType.GOLD_PRICE: ["黄金", "金价", "避险"],
    EventType.FUND_FLOW: ["资金流入", "资金流出", "北向资金", "南向资金", "主力资金"],
    EventType.TECH_BREAKTHROUGH: ["突破", "创新", "技术进展", "量产", "首发"],
    EventType.INDUSTRY_CYCLE: ["景气度", "周期", "上行", "下行", "复苏"],
    EventType.SUPPLY_DISRUPTION: ["断供", "缺货", "产能不足", "供应链"],
    EventType.BLACK_SWAN: ["黑天鹅", "崩盘", "暴跌", "系统性风险"],
}


@dataclass
class ClassifiedEvent:
    """Result of event classification."""
    event_type: EventType
    category: EventCategory
    polarity: float
    magnitude: float
    time_horizon: Literal["short", "medium", "long"] = "medium"
    keywords_matched: list[str] = field(default_factory=list)


def get_event_type(type_name: str) -> EventType:
    """Get EventType by name string."""
    for et in EventType:
        if et.value == type_name:
            return et
    return EventType.OTHER


def classify_event(text: str) -> ClassifiedEvent:
    """Rule-based event classification from text."""
    text_lower = text.lower() if text else ""
    best_match = None
    best_count = 0

    for event_type, keywords in EVENT_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text_lower or kw in text]
        if len(matched) > best_count:
            best_count = len(matched)
            best_match = (event_type, matched)

    if best_match:
        event_type, keywords_matched = best_match
    else:
        event_type = EventType.OTHER
        keywords_matched = []

    # Determine category
    category = EventCategory.MACRO
    for cat, types in EVENT_HIERARCHY.items():
        if event_type in types:
            category = cat
            break

    # Default polarity
    polarity_map = {
        EventType.EARNINGS_SURPRISE: 0.7,
        EventType.EARNINGS_MISS: -0.7,
        EventType.RATE_CHANGE: -0.3,
        EventType.POLICY_SHIFT: 0.0,
        EventType.BLACK_SWAN: -0.9,
        EventType.TECH_BREAKTHROUGH: 0.6,
        EventType.FUND_FLOW: 0.3,
        EventType.MARKET_CRASH: -0.9,
    }
    polarity = polarity_map.get(event_type, 0.0)

    magnitude_map = {
        EventType.BLACK_SWAN: 0.9,
        EventType.MARKET_CRASH: 0.8,
        EventType.EARNINGS_SURPRISE: 0.6,
        EventType.RATE_CHANGE: 0.5,
    }
    magnitude = magnitude_map.get(event_type, 0.5)

    return ClassifiedEvent(
        event_type=event_type,
        category=category,
        polarity=polarity,
        magnitude=magnitude,
        time_horizon="medium",
        keywords_matched=keywords_matched,
    )