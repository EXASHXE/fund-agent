"""Knowledge Graph schema: node types, edge types, data classes.

Design: Dataclasses store node/edge data. NetworkX uses string node IDs
(e.g. "fund:110011") as nodes, with dataclass instances in G.nodes[id]["data"].
All node dataclasses are mutable (not frozen) for convenience.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class KGNodeType(Enum):
    FUND = "fund"
    STOCK = "stock"
    INDUSTRY = "industry"
    THEME = "theme"
    EVENT = "event"
    MACRO_FACTOR = "macro_factor"
    SUPPLY_CHAIN = "supply_chain"


class KGEdgeType(Enum):
    HOLDS = "holds"
    BELONGS_TO = "belongs_to"
    IN_THEME = "in_theme"
    IMPACTS = "impacts"
    CORRELATES_WITH = "correlates"
    EXPOSES = "exposes"
    EXPOSED_TO = "exposed_to"
    AFFECTED_BY = "affected_by"
    SUPPLIES = "supplies"
    COMPETES_WITH = "competes_with"


@dataclass
class KGEdge:
    """Edge in the knowledge graph."""
    source: str
    target: str
    edge_type: KGEdgeType
    weight: float | None = None
    polarity: float | None = None
    magnitude: float | None = None


@dataclass
class FundNode:
    """Fund node data."""
    code: str = ""
    name: str = ""
    fund_type: str = ""
    style: str = ""
    size: str = ""
    manager: str = ""
    nav_date: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.FUND

    @property
    def id(self) -> str:
        return f"fund:{self.code}"


@dataclass
class StockNode:
    """Stock node data."""
    code: str = ""
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.STOCK

    @property
    def id(self) -> str:
        return f"stock:{self.code}"


@dataclass
class IndustryNode:
    """Industry node data."""
    code: str = ""
    name: str = ""
    sw_code: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.INDUSTRY

    @property
    def id(self) -> str:
        return f"industry:{self.code}"


@dataclass
class ThemeNode:
    """Theme node data."""
    name: str = ""
    keywords: list[str] = field(default_factory=list)

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.THEME

    @property
    def id(self) -> str:
        return f"theme:{self.name}"


@dataclass
class EventNode:
    """Event node data."""
    event_id: str = ""
    event_type: str = ""
    subtype: str = ""
    date: str = ""
    polarity: float = 0.0
    magnitude: float = 0.0
    time_horizon: str = "medium"
    description: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.EVENT

    @property
    def id(self) -> str:
        return f"event:{self.event_id}"


@dataclass
class MacroFactorNode:
    """Macro factor node data."""
    name: str = ""
    factor_type: str = ""
    direction: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.MACRO_FACTOR

    @property
    def id(self) -> str:
        return f"macro:{self.name}"


@dataclass
class SupplyChainNode:
    """Supply chain node data."""
    name: str = ""
    tier: str = ""
    products: list[str] = field(default_factory=list)
    region: str = ""

    @property
    def node_type(self) -> KGNodeType:
        return KGNodeType.SUPPLY_CHAIN

    @property
    def id(self) -> str:
        return f"supply_chain:{self.name}"