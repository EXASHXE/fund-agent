# Phase 1: Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Knowledge Graph, Qdrant vector store, event taxonomy, LangGraph agent skeleton, and scoring type foundations without touching existing working code.

**Architecture:** All new modules are additive — no modifications to existing code. KG uses NetworkX in-memory graph. Qdrant runs locally with Python client. LangGraph state graph defines the multi-agent orchestrator skeleton. Score types define the data contracts for Phase 3 scoring system.

**Tech Stack:** NetworkX, Qdrant Python client, LangGraph, Pydantic v2, pytest

**Key Constraint:** `python -m src.cli analyze` must still work identically after all Phase 1 changes. No existing files are modified except `requirements.txt` and `src/config/defaults.py` (additive only).

---

## File Structure (Phase 1 creates these)

```
src/kg/
├── __init__.py          # Module entry point
├── schema.py            # KGNodeType, KGEdgeType, KGNode, KGEdge dataclasses
├── graph.py             # KnowledgeGraphBuilder class
├── industry_map.py      # SW industry → theme mapping
└── enrichment.py        # Event enrichment (add events to KG)

src/vectorstore/
├── __init__.py          # Module entry point
├── client.py            # QdrantClient wrapper, collection management
├── embedding.py         # OpenAI-compatible embedding pipeline
├── collections.py       # Collection definitions, schema
└── search.py            # Search utilities

src/events/
├── __init__.py          # Module entry point
├── taxonomy.py          # Event type hierarchy
└── extractor.py         # LLM event extraction (stub for Phase 2)

src/analysis/scoring/
├── __init__.py          # Module entry point
└── types.py             # ScoreComponent, MarketRegime, CompositeScore

src/agents/
├── __init__.py          # (overwrite existing)
├── graph.py             # LangGraph StateGraph definition
├── state.py             # FundResearchState TypedDict
└── supervisor.py         # Supervisor routing logic

requirements.txt         # Add: networkx, qdrant-client, langgraph, langchain-core
```

---

### Task 1: Add Dependencies and Create Module Directories

**Files:**
- Modify: `requirements.txt`
- Create: `src/kg/__init__.py`, `src/vectorstore/__init__.py`, `src/events/__init__.py`
- Modify: `src/analysis/scoring/__init__.py` (create directory, keep existing parent `src/analysis/scoring/`)

- [ ] **Step 1: Add new dependencies to requirements.txt**

Append the following to `requirements.txt`:

```
# Phase 1: Infrastructure dependencies
networkx>=3.2
qdrant-client>=1.7.0
langgraph>=0.2.0
langchain-core>=0.3.0
```

- [ ] **Step 2: Create module directories and `__init__.py` files**

```bash
mkdir -p src/kg src/vectorstore src/events
touch src/kg/__init__.py src/vectorstore/__init__.py src/events/__init__.py
```

- [ ] **Step 3: Create `src/analysis/scoring/` directory**

The `src/analysis/scoring/` directory currently exists with `macro.py`, `meso.py`, `micro.py`. We need to add `__init__.py` and `types.py`. Create `src/analysis/scoring/__init__.py`:

```python
# Phase 1: Scoring types loaded on demand
from src.analysis.scoring.types import ScoreComponent, MarketRegime, CompositeScore

__all__ = ["ScoreComponent", "MarketRegime", "CompositeScore"]
```

- [ ] **Step 4: Install dependencies and verify imports**

Run: `pip install -r requirements.txt`
Then verify: `python -c "import networkx; import qdrant_client; import langgraph; print('OK')"`

- [ ] **Step 5: Run existing tests to confirm no breakage**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests pass (same skip/fail count as before)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/kg/__init__.py src/vectorstore/__init__.py src/events/__init__.py src/analysis/scoring/__init__.py
git commit -m "feat(phase1): add infrastructure dependencies and module directories"
```

---

### Task 2: Knowledge Graph Schema and Industry Mapping

**Files:**
- Create: `src/kg/schema.py`
- Create: `src/kg/industry_map.py`
- Test: `tests/test_kg_schema.py`

- [ ] **Step 1: Write the failing test for KG schema**

Create `tests/test_kg_schema.py`:

```python
import pytest
from src.kg.schema import (
    KGNodeType, KGEdgeType, KGNode, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode
)


class TestKGSchema:
    def test_node_types_enum(self):
        assert KGNodeType.FUND.value == "fund"
        assert KGNodeType.STOCK.value == "stock"
        assert KGNodeType.INDUSTRY.value == "industry"
        assert KGNodeType.THEME.value == "theme"
        assert KGNodeType.EVENT.value == "event"
        assert KGNodeType.MACRO_FACTOR.value == "macro_factor"

    def test_edge_types_enum(self):
        assert KGEdgeType.HOLDS.value == "holds"
        assert KGEdgeType.BELONGS_TO.value == "belongs_to"
        assert KGEdgeType.IN_THEME.value == "in_theme"
        assert KGEdgeType.IMPACTS.value == "impacts"
        assert KGEdgeType.CORRELATES_WITH.value == "correlates"
        assert KGEdgeType.EXPOSES.value == "exposes"

    def test_fund_node_creation(self):
        node = FundNode(code="110011", name="易方达中小盘混合", fund_type="hybrid", style="growth")
        assert node.node_type == KGNodeType.FUND
        assert node.code == "110011"
        assert node.style == "growth"

    def test_stock_node_creation(self):
        node = StockNode(code="600519", name="贵州茅台", sector="白酒", industry="食品饮料")
        assert node.node_type == KGNodeType.STOCK
        assert node.code == "600519"

    def test_event_node_creation(self):
        node = EventNode(
            event_id="evt_001",
            event_type="rate_change",
            subtype="fed_rate_decision",
            date="2026-05-27",
            polarity=-0.7,
            magnitude=0.8,
            time_horizon="medium",
            description="美联储维持利率不变"
        )
        assert node.node_type == KGNodeType.EVENT
        assert node.polarity == -0.7
        assert node.magnitude == 0.8

    def test_kg_edge_creation(self):
        edge = KGEdge(
            source="110011",
            target="600519",
            edge_type=KGEdgeType.HOLDS,
            weight=0.095
        )
        assert edge.edge_type == KGEdgeType.HOLDS
        assert edge.weight == 0.095
        assert edge.source == "110011"

    def test_edge_with_polarity(self):
        edge = KGEdge(
            source="evt_001",
            target="600519",
            edge_type=KGEdgeType.IMPACTS,
            polarity=-0.5,
            magnitude=0.7
        )
        assert edge.polarity == -0.5

    def test_industry_node(self):
        node = IndustryNode(code="sw_food_beverage", name="食品饮料", sw_code="801120")
        assert node.node_type == KGNodeType.INDUSTRY

    def test_theme_node(self):
        node = ThemeNode(name="AI算力", keywords=["人工智能", "算力", "GPU", "光模块"])
        assert node.node_type == KGNodeType.THEME
        assert len(node.keywords) == 4

    def test_macro_factor_node(self):
        node = MacroFactorNode(name="利率", factor_type="interest_rate", direction="rising")
        assert node.node_type == KGNodeType.MACRO_FACTOR
        assert node.direction == "rising"


class TestIndustryMap:
    def test_industry_to_theme_mapping(self):
        from src.kg.industry_map import INDUSTRY_THEME_MAP, THEME_KEYWORDS
        # Every industry should map to at least one theme
        assert len(INDUSTRY_THEME_MAP) >= 20
        # Every theme should have keywords
        assert len(THEME_KEYWORDS) >= 10
        # Spot check known mappings
        assert "食品饮料" in INDUSTRY_THEME_MAP or "sw_food_beverage" in INDUSTRY_THEME_MAP

    def test_theme_keywords_non_empty(self):
        from src.kg.industry_map import THEME_KEYWORDS
        for theme, keywords in THEME_KEYWORDS.items():
            assert len(keywords) >= 2, f"Theme '{theme}' has fewer than 2 keywords: {keywords}"

    def test_get_themes_for_industry(self):
        from src.kg.industry_map import get_themes_for_industry
        themes = get_themes_for_industry("电子")
        assert isinstance(themes, list)
        # Electronics maps to semiconductor/AI themes
        assert len(themes) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_kg_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.kg.schema'`

- [ ] **Step 3: Create `src/kg/schema.py`**

```python
"""Knowledge Graph schema: node types, edge types, data classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class KGNodeType(Enum):
    FUND = "fund"
    STOCK = "stock"
    INDUSTRY = "industry"
    THEME = "theme"
    EVENT = "event"
    MACRO_FACTOR = "macro_factor"


class KGEdgeType(Enum):
    HOLDS = "holds"
    BELONGS_TO = "belongs_to"
    IN_THEME = "in_theme"
    IMPACTS = "impacts"
    CORRELATES_WITH = "correlates"
    EXPOSES = "exposes"


@dataclass
class KGNode:
    """Base class for all KG nodes."""
    node_type: KGNodeType
    id: str

    def __hash__(self):
        return hash((self.node_type.value, self.id))

    def __eq__(self, other):
        if not isinstance(other, KGNode):
            return NotImplemented
        return self.node_type == other.node_type and self.id == other.id


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
class FundNode(KGNode):
    code: str = ""
    name: str = ""
    fund_type: str = ""
    style: str = ""
    size: str = ""
    manager: str = ""
    nav_date: str = ""

    def __post_init__(self):
        self.node_type = KGNodeType.FUND
        self.id = f"fund:{self.code}"


@dataclass
class StockNode(KGNode):
    code: str = ""
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: str = ""

    def __post_init__(self):
        self.node_type = KGNodeType.STOCK
        self.id = f"stock:{self.code}"


@dataclass
class IndustryNode(KGNode):
    code: str = ""
    name: str = ""
    sw_code: str = ""

    def __post_init__(self):
        self.node_type = KGNodeType.INDUSTRY
        self.id = f"industry:{self.code}"


@dataclass
class ThemeNode(KGNode):
    name: str = ""
    keywords: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.node_type = KGNodeType.THEME
        self.id = f"theme:{self.name}"


@dataclass
class EventNode(KGNode):
    event_id: str = ""
    event_type: str = ""
    subtype: str = ""
    date: str = ""
    polarity: float = 0.0
    magnitude: float = 0.0
    time_horizon: Literal["short", "medium", "long"] = "medium"
    description: str = ""

    def __post_init__(self):
        self.node_type = KGNodeType.EVENT
        self.id = f"event:{self.event_id}"


@dataclass
class MacroFactorNode(KGNode):
    name: str = ""
    factor_type: str = ""
    direction: str = ""

    def __post_init__(self):
        self.node_type = KGNodeType.MACRO_FACTOR
        self.id = f"macro:{self.name}"
```

- [ ] **Step 4: Create `src/kg/industry_map.py`**

```python
"""SW industry → investment theme mapping and theme keyword definitions."""
from __future__ import annotations

# SW industry name → list of theme names
INDUSTRY_THEME_MAP: dict[str, list[str]] = {
    "电子": ["半导体", "AI算力", "消费电子"],
    "半导体": ["半导体", "AI算力"],
    "计算机": ["AI算力", "数字经济", "信创"],
    "通信": ["5G", "数字经济"],
    "传媒": ["数字经济", "AI算力"],
    "电力设备": ["新能源", "储能"],
    "新能源": ["新能源", "储能", "光伏"],
    "汽车": ["新能源车", "智能驾驶"],
    "汽车零部件": ["新能源车", "智能驾驶"],
    "医药生物": ["医药", "创新药", "医疗器械"],
    "食品饮料": ["消费", "白酒"],
    "白酒": ["消费", "白酒"],
    "银行": ["金融", "红利"],
    "非银金融": ["金融"],
    "房地产": ["房地产", "周期"],
    "煤炭": ["周期", "红利"],
    "石油石化": ["周期", "能源"],
    "有色金属": ["周期", "新能源"],
    "钢铁": ["周期"],
    "基础化工": ["周期", "新材料"],
    "建筑材料": ["周期", "房地产"],
    "国防军工": ["军工", "国产替代"],
    "农林牧渔": ["消费", "农业"],
    "家用电器": ["消费", "智能驾驶"],
    "轻工制造": ["消费"],
    "商贸零售": ["消费"],
    "社会服务": ["消费", "旅游"],
    "纺织服饰": ["消费"],
    "美容护理": ["消费", "医药"],
    "公用事业": ["红利", "新能源"],
    "交通运输": ["周期", "物流"],
    "环保": ["新能源", "环保"],
    "机械设备": ["周期", "新能源", "智能制造"],
}

# Theme name → keyword list for news matching
THEME_KEYWORDS: dict[str, list[str]] = {
    "半导体": ["芯片", "晶圆", "光刻", "半导体", "集成电路", "封测", "设计", "设备"],
    "AI算力": ["AI", "人工智能", "大模型", "算力", "GPU", "光模块", "服务器", "智算"],
    "消费电子": ["手机", "VR", "AR", "可穿戴", "AirPods", "折叠屏"],
    "数字经济": ["数字", "云计算", "大数据", "数字化"],
    "信创": ["信创", "国产化", "国产替代", "操作系统", "数据库"],
    "5G": ["5G", "基站", "光通信", "通信设备"],
    "新能源": ["光伏", "风电", "新能源", "碳中和", "绿电", "充电桩"],
    "储能": ["储能", "电池", "锂电", "钠电", "固态电池"],
    "光伏": ["光伏", "硅料", "硅片", "组件", "逆变器"],
    "新能源车": ["电动车", "锂电池", "充电", "新能源车", "智能座驾"],
    "智能驾驶": ["自动驾驶", "智能驾驶", "激光雷达", "车路协同"],
    "医药": ["医药", "集采", "医保", "处方药", "OTC"],
    "创新药": ["创新药", "BD", "临床", "ADC", "GLP-1", "PD-1"],
    "医疗器械": ["医疗器械", "医疗设备", "IVD", "高值耗材"],
    "消费": ["消费", "内需", "零售", "品牌"],
    "白酒": ["白酒", "茅台", "五粮液", "次高端", "高端白酒"],
    "金融": ["银行", "保险", "券商", "利息", "LPR"],
    "红利": ["红利", "高股息", "分红", "防御"],
    "周期": ["周期", "产能", "涨价", "库存"],
    "能源": ["原油", "天然气", "石油", "能源", "OPEC"],
    "房地产": ["房地产", "楼盘", "销售", "土地", "限购"],
    "军工": ["军工", "国防", "装备", "军费"],
    "国产替代": ["国产替代", "自主可控", "卡脖子", "技术封锁"],
    "农业": ["种业", "粮食", "猪周期", "饲料"],
    "环保": ["环保", "碳中和", "碳交易", "ESG"],
    "智能制造": ["机器人", "自动化", "工业互联网", "3D打印"],
    "物流": ["物流", "快递", "供应链", "冷链"],
    "旅游": ["旅游", "酒店", "出境游", "免税"],
    "新材料": ["新材料", "碳纤维", "石墨烯", "透明陶瓷"],
}


def get_themes_for_industry(industry_name: str) -> list[str]:
    """Get investment themes associated with an SW industry name.

    Args:
        industry_name: SW industry name (e.g., "电子", "医药生物")

    Returns:
        List of theme names. Empty list if industry not found.
    """
    return INDUSTRY_THEME_MAP.get(industry_name, [])


def get_keywords_for_theme(theme_name: str) -> list[str]:
    """Get search keywords associated with an investment theme.

    Args:
        theme_name: Theme name (e.g., "半导体", "AI算力")

    Returns:
        List of keywords. Empty list if theme not found.
    """
    return THEME_KEYWORDS.get(theme_name, [])


def get_all_themes() -> list[str]:
    """Get all defined theme names."""
    return list(THEME_KEYWORDS.keys())


def get_all_industries() -> list[str]:
    """Get all defined SW industry names."""
    return list(INDUSTRY_THEME_MAP.keys())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_kg_schema.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/kg/schema.py src/kg/industry_map.py tests/test_kg_schema.py
git commit -m "feat(kg): add knowledge graph schema and industry-theme mapping"
```

---

### Task 3: Knowledge Graph Builder

**Files:**
- Create: `src/kg/graph.py`
- Create: `src/kg/enrichment.py`
- Test: `tests/test_kg_graph.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_kg_graph.py`:

```python
import pytest
from src.kg.graph import KnowledgeGraphBuilder
from src.kg.schema import KGNodeType, KGEdgeType


@pytest.fixture
def sample_fund_data():
    return {
        "code": "110011",
        "name": "易方达中小盘混合",
        "fund_type": "hybrid",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            {"stock_code": "601318", "stock_name": "中国平安", "weight": 5.1},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
            {"industry": "金融", "weight": 15.2},
        ],
    }


class TestKnowledgeGraphBuilder:
    def test_build_from_holdings_creates_fund_node(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Should have fund node
        fund_id = f"fund:{sample_fund_data['code']}"
        assert fund_id in [n.id for n in graph.nodes]

    def test_build_from_holdings_creates_stock_nodes(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Should have 3 stock nodes
        stock_nodes = [n for n in graph.nodes if n.node_type == KGNodeType.STOCK]
        assert len(stock_nodes) == 3

    def test_build_from_holdings_creates_hold_edges(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Should have 3 HOLDS edges with weights
        hold_edges = [e for e in graph.edges if e.edge_type == KGEdgeType.HOLDS]
        assert len(hold_edges) == 3
        # First holding should have weight 9.5
       茅台_edge = [e for e in hold_edges if e.target == "stock:600519"][0]
        assert 茅台_edge.weight == pytest.approx(9.5)

    def test_build_from_holdings_creates_industry_nodes(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Should have industry nodes from sectors data
        industry_nodes = [n for n in graph.nodes if n.node_type == KGNodeType.INDUSTRY]
        assert len(industry_nodes) >= 2

    def test_build_creates_belongs_to_edges(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Stock nodes should have BELONGS_TO edges to industries
        belongs_edges = [e for e in graph.edges if e.edge_type == KGEdgeType.BELONGS_TO]
        # At least some stocks should map to industries
        assert len(belongs_edges) >= 1

    def test_query_relevance_for_fund_news(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Query relevance of a news item mentioning 茅台
        news = {"title": "贵州茅台发布年报", "entities": ["600519"]}
        relevance = kg.query_relevance(graph, sample_fund_data["code"], news)
        # Should have high relevance since 茅台 is a top holding
        assert relevance > 0.3

    def test_query_relevance_for_unrelated_news(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        # Query relevance of a news item about unrelated stock
        news = {"title": "某生物医药公司上市", "entities": ["300999"]}
        relevance = kg.query_relevance(graph, sample_fund_data["code"], news)
        # Should have low relevance
        assert relevance < 0.2

    def test_get_fund_exposure(self, sample_fund_data):
        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)
        exposure = kg.get_fund_exposure(graph, sample_fund_data["code"])
        # Should return dict with industries, themes, macro_factors
        assert "industries" in exposure
        assert "themes" in exposure
        # Food & beverage should be a major industry
        assert any("食品饮料" in ind for ind in exposure["industries"])

    def test_enrich_with_events(self, sample_fund_data):
        from src.kg.schema import EventNode
        from src.kg.enrichment import enrich_with_events

        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        event = EventNode(
            event_id="evt_001",
            event_type="earnings_surprise",
            subtype="positive",
            date="2026-05-27",
            polarity=0.8,
            magnitude=0.6,
            time_horizon="short",
            description="贵州茅台Q1净利润超预期20%"
        )

        graph = enrich_with_events(graph, [event], affected_entities=["stock:600519"])

        # Should have event node
        event_nodes = [n for n in graph.nodes if n.node_type == KGNodeType.EVENT]
        assert len(event_nodes) == 1

        # Should have IMPACTS edge from event to stock
        impact_edges = [e for e in graph.edges if e.edge_type == KGEdgeType.IMPACTS]
        assert len(impact_edges) == 1
        assert impact_edges[0].polarity == pytest.approx(0.8)

    def test_get_impact_chain(self, sample_fund_data):
        from src.kg.schema import EventNode
        from src.kg.enrichment import enrich_with_events

        kg = KnowledgeGraphBuilder()
        graph = kg.build_from_holdings(sample_fund_data)

        event = EventNode(
            event_id="evt_001",
            event_type="earnings_surprise",
            subtype="positive",
            date="2026-05-27",
            polarity=0.8,
            magnitude=0.6,
            time_horizon="short",
            description="贵州茅台Q1净利润超预期"
        )
        graph = enrich_with_events(graph, [event], affected_entities=["stock:600519"])

        # Get impact chain from event to fund
        impact = kg.get_impact_chain(graph, "evt_001", sample_fund_data["code"])
        # Should find: event → stock(茅台) → fund(110011) with polarity
        assert impact["total_polarity"] != 0
        assert len(impact["paths"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_kg_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.kg.graph'`

- [ ] **Step 3: Create `src/kg/graph.py`**

```python
"""Knowledge Graph builder: construct and query the fund-stock-industry-event graph."""
from __future__ import annotations

from typing import Any

import networkx as nx

from src.kg.schema import (
    KGNodeType, KGEdgeType, KGNode, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.kg.industry_map import get_themes_for_industry, get_keywords_for_theme


class KnowledgeGraphBuilder:
    """Build and query a knowledge graph from fund holdings data."""

    def build_from_holdings(self, fund_data: dict) -> nx.DiGraph:
        """Build KG from fund holdings data.

        Args:
            fund_data: Dict with keys: code, name, fund_type, holdings, sectors.

        Returns:
            NetworkX DiGraph with fund, stock, industry, theme nodes and edges.
        """
        G = nx.DiGraph()

        # Create fund node
        fund_node = FundNode(
            code=fund_data["code"],
            name=fund_data.get("name", ""),
            fund_type=fund_data.get("fund_type", ""),
            style=fund_data.get("style", ""),
        )
        G.add_node(fund_node)

        # Create stock nodes and HOLDS edges
        holdings = fund_data.get("holdings", [])
        stock_industry_map = {}  # stock_code -> industry_name

        for holding in holdings:
            stock_node = StockNode(
                code=holding["stock_code"],
                name=holding.get("stock_name", ""),
                sector=holding.get("sector", ""),
                industry=holding.get("industry", ""),
            )
            G.add_node(stock_node)

            # HOLDS edge with weight
            holds_edge = KGEdge(
                source=f"fund:{fund_data['code']}",
                target=f"stock:{holding['stock_code']}",
                edge_type=KGEdgeType.HOLDS,
                weight=holding.get("weight", 0),
            )
            G.add_edge(fund_node.id, stock_node.id, edge_data=holds_edge)

            # Track stock → industry mapping for later
            if holding.get("industry"):
                stock_industry_map[holding["stock_code"]] = holding["industry"]

        # Create industry nodes from sectors data
        sectors = fund_data.get("sectors", [])
        for sector_info in sectors:
            industry_name = sector_info.get("industry", "")
            if not industry_name:
                continue

            industry_node = IndustryNode(
                code=f"sw_{industry_name}",
                name=industry_name,
                sw_code=sector_info.get("sw_code", ""),
            )
            G.add_node(industry_node)

            # EXPOSES edge: fund → industry
            exposes_edge = KGEdge(
                source=f"fund:{fund_data['code']}",
                target=industry_node.id,
                edge_type=KGEdgeType.EXPOSES,
                weight=sector_info.get("weight", 0),
            )
            G.add_edge(fund_node.id, industry_node.id, edge_data=exposes_edge)

            # Create theme nodes and IN_THEME edges
            themes = get_themes_for_industry(industry_name)
            for theme_name in themes:
                theme_node = ThemeNode(name=theme_name, keywords=get_keywords_for_theme(theme_name))
                # Only add if not already present
                if not G.has_node(theme_node.id):
                    G.add_node(theme_node)
                # Industry IN_THEME
                in_theme_edge = KGEdge(
                    source=industry_node.id,
                    target=theme_node.id,
                    edge_type=KGEdgeType.IN_THEME,
                )
                G.add_edge(industry_node.id, theme_node.id, edge_data=in_theme_edge)

        # Create BELONGS_TO edges from stock to industry
        for stock_code, industry_name in stock_industry_map.items():
            stock_id = f"stock:{stock_code}"
            industry_id = f"industry:sw_{industry_name}"
            if G.has_node(stock_id) and G.has_node(industry_id):
                belongs_edge = KGEdge(
                    source=stock_id,
                    target=industry_id,
                    edge_type=KGEdgeType.BELONGS_TO,
                )
                G.add_edge(stock_id, industry_id, edge_data=belongs_edge)

        # Also infer industry from sectors for stocks that don't have explicit industry
        for holding in holdings:
            stock_id = f"stock:{holding['stock_code']}"
            if not G.has_node(stock_id):
                continue
            # Check if stock already has BELONGS_TO edge
            out_edges = G.out_edges(stock_id)
            has_belongs = any(
                G.edges[src, dst].get("edge_data", KGEdge("", "", KGEdgeType.HOLDS)).edge_type == KGEdgeType.BELONGS_TO
                for src, dst in out_edges
            )
            if not has_belongs:
                # Infer from sectors
                for sector_info in sectors:
                    industry_name = sector_info.get("industry", "")
                    industry_id = f"industry:sw_{industry_name}"
                    if G.has_node(industry_id):
                        belongs_edge = KGEdge(
                            source=stock_id,
                            target=industry_id,
                            edge_type=KGEdgeType.BELONGS_TO,
                        )
                        G.add_edge(stock_id, industry_id, edge_data=belongs_edge)
                        break  # Only assign to first matching industry

        return G

    def query_relevance(
        self,
        graph: nx.DiGraph,
        fund_code: str,
        news_item: dict,
        stock_hit_weight: float = 0.25,
        top10_hit_weight: float = 0.20,
        industry_hit_weight: float = 0.15,
        theme_hit_weight: float = 0.10,
        timeliness_weight: float = 0.10,
        severity_weight: float = 0.10,
    ) -> float:
        """Query KG for fund-news relevance score.

        Multi-factor relevance:
        - holding overlap (stock names/codes mentioned in news)
        - top-10 holding hit
        - industry hit
        - theme hit
        - timeliness (time decay)
        - sentiment severity
        """
        fund_id = f"fund:{fund_code}"
        if not graph.has_node(fund_id):
            return 0.0

        # Get fund's holdings
        hold_edges = [
            (src, dst, data) for src, dst, data in graph.edges(data=True)
            if src == fund_id and data.get("edge_data", KGEdge("", "", KGEdgeType.HOLDS)).edge_type == KGEdgeType.HOLDS
        ]

        holding_codes = set()
        total_weight = 0.0
        for _, dst, data in hold_edges:
            edge = data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.HOLDS:
                stock_code = dst.replace("stock:", "")
                holding_codes.add(stock_code)
                total_weight += edge.weight or 0

        # Get fund's industries and themes
        fund_industries = set()
        fund_themes = set()
        for _, dst, data in graph.edges(fund_id, data=True):
            edge = data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.EXPOSES:
                fund_industries.add(dst)
            elif edge and edge.edge_type == KGEdgeType.HOLDS:
                pass  # Already handled

        # Traverse: industry → theme
        for ind_id in fund_industries:
            for _, theme_dst, _ in graph.edges(ind_id, data=True):
                fund_themes.add(theme_dst)

        # Check news entity overlap with holdings
        news_entities = set(news_item.get("entities", []))
        news_title = news_item.get("title", "")

        holding_hit = 0.0
        for code in holding_codes:
            if code in news_entities or code in news_title:
                holding_hit = 1.0
                break

        # Industry hit
        industry_hit = 0.0
        for ind_id in fund_industries:
            ind_name = ind_id.replace("industry:sw_", "")
            if ind_name in news_title:
                industry_hit = 1.0
                break

        # Theme hit
        theme_hit = 0.0
        keywords_all = set()
        for theme_id in fund_themes:
            theme_name = theme_id.replace("theme:", "")
            keywords_all.update(get_keywords_for_theme(theme_name))
            if theme_name in news_title:
                theme_hit = 1.0
                break

        if theme_hit == 0.0:
            for kw in keywords_all:
                if kw in news_title:
                    theme_hit = 0.5
                    break

        # Timeliness (default 1.0 if no date, decay computed externally)
        timeliness = 1.0

        # Severity (default 0.5 if not provided)
        severity = abs(news_item.get("sentiment", 0.5))

        relevance = (
            holding_hit * stock_hit_weight
            + min(1.0, holding_hit) * top10_hit_weight  # top-10 overlap same as holding hit
            + industry_hit * industry_hit_weight
            + theme_hit * theme_hit_weight
            + timeliness * timeliness_weight
            + severity * severity_weight
        )

        return min(1.0, relevance)

    def get_fund_exposure(self, graph: nx.DiGraph, fund_code: str) -> dict:
        """Get fund's industry/theme/macro exposure profile from KG."""
        fund_id = f"fund:{fund_code}"
        if not graph.has_node(fund_id):
            return {"industries": [], "themes": [], "macro_factors": []}

        industries = []
        themes = []
        macro_factors = []

        for _, dst, data in graph.edges(fund_id, data=True):
            edge = data.get("edge_data")
            if not edge:
                continue
            if edge.edge_type == KGEdgeType.EXPOSES:
                ind_name = dst.replace("industry:sw_", "")
                industries.append({"name": ind_name, "weight": edge.weight or 0})

        # Get themes through industry → theme edges
        for ind_id in [ind["name"] for ind in industries]:
            full_ind_id = f"industry:sw_{ind_id}" if not ind_id.startswith("industry:") else ind_id
            for _, theme_dst, _ in graph.edges(full_ind_id, data=True):
                edge = data.get("edge_data") if data else None
                theme_name = theme_dst.replace("theme:", "")
                themes.append(theme_name)

        return {
            "industries": list(set(ind["name"] for ind in industries)),
            "themes": list(set(themes)),
            "macro_factors": macro_factors,  # Populated via enrichment
        }

    def get_impact_chain(self, graph: nx.DiGraph, event_id: str, fund_code: str) -> dict:
        """Trace event impact through KG to affected funds.

        Returns:
            Dict with total_polarity, total_magnitude, paths list.
        """
        event_node_id = f"event:{event_id}"
        fund_id = f"fund:{fund_code}"

        if not graph.has_node(event_node_id) or not graph.has_node(fund_id):
            return {"total_polarity": 0.0, "total_magnitude": 0.0, "paths": []}

        # Find all paths from event to fund
        paths = []
        total_polarity = 0.0
        total_magnitude = 0.0

        # Direct: event → stock → fund (via HOLDS reverse)
        for _, stock_dst, impact_data in graph.edges(event_node_id, data=True):
            impact_edge = impact_data.get("edge_data")
            if impact_edge and impact_edge.edge_type == KGEdgeType.IMPACTS:
                # Check if this stock is held by the fund
                for fund_src, _, hold_data in graph.in_edges(stock_dst, data=True):
                    if fund_src == fund_id:
                        hold_edge = hold_data.get("edge_data")
                        if hold_edge and hold_edge.edge_type == KGEdgeType.HOLDS:
                            hold_weight = hold_edge.weight or 0
                            path_polarity = (impact_edge.polarity or 0) * (hold_weight / 100.0)
                            path_magnitude = (impact_edge.magnitude or 0) * (hold_weight / 100.0)
                            total_polarity += path_polarity
                            total_magnitude += path_magnitude
                            paths.append({
                                "event": event_id,
                                "stock": stock_dst,
                                "fund": fund_id,
                                "polarity": impact_edge.polarity,
                                "magnitude": impact_edge.magnitude,
                                "hold_weight": hold_weight,
                            })

        # Indirect: event → industry → fund (via EXPOSES reverse)
        for _, ind_dst, impact_data in graph.edges(event_node_id, data=True):
            impact_edge = impact_data.get("edge_data")
            if impact_edge and impact_edge.edge_type == KGEdgeType.IMPACTS:
                # Check if fund has EXPOSES to this industry
                for fund_src, _, expose_data in graph.in_edges(ind_dst, data=True):
                    if fund_src == fund_id:
                        expose_edge = expose_data.get("edge_data")
                        if expose_edge and expose_edge.edge_type == KGEdgeType.EXPOSES:
                            exposure_weight = expose_edge.weight or 0
                            path_polarity = (impact_edge.polarity or 0) * (exposure_weight / 100.0)
                            path_magnitude = (impact_edge.magnitude or 0) * (exposure_weight / 100.0)
                            total_polarity += path_polarity
                            total_magnitude += path_magnitude
                            paths.append({
                                "event": event_id,
                                "industry": ind_dst,
                                "fund": fund_id,
                                "polarity": impact_edge.polarity,
                                "magnitude": impact_edge.magnitude,
                                "exposure_weight": exposure_weight,
                            })

        return {
            "total_polarity": round(total_polarity, 4),
            "total_magnitude": round(total_magnitude, 4),
            "paths": paths,
        }
```

- [ ] **Step 4: Create `src/kg/enrichment.py`**

```python
"""Knowledge graph enrichment: add events and update impact edges."""
from __future__ import annotations

import networkx as nx

from src.kg.schema import KGEdgeType, EventNode


def enrich_with_events(
    graph: nx.DiGraph,
    events: list[EventNode],
    affected_entities: list[str] | None = None,
) -> nx.DiGraph:
    """Add event nodes and IMPACTS edges to the knowledge graph.

    Args:
        graph: Existing KG to enrich.
        events: List of EventNode objects to add.
        affected_entities: List of entity IDs (e.g., "stock:600519") affected by events.
            If None, events are added without IMPACTS edges.

    Returns:
        Enriched graph (modified in place, also returned for convenience).
    """
    affected_entities = affected_entities or []

    for event in events:
        # Add event node
        graph.add_node(event)

        # Create IMPACTS edges to affected entities
        if affected_entities:
            for entity_id in affected_entities:
                if graph.has_node(entity_id):
                    impact_edge = KGEdge(
                        source=event.id,
                        target=entity_id,
                        edge_type=KGEdgeType.IMPACTS,
                        polarity=event.polarity,
                        magnitude=event.magnitude,
                    )
                    graph.add_edge(event.id, entity_id, edge_data=impact_edge)

    return graph
```

- [ ] **Step 5: Update `src/kg/__init__.py`**

```python
"""Knowledge Graph module: build, query, and enrich fund research graph."""
from src.kg.graph import KnowledgeGraphBuilder
from src.kg.schema import (
    KGNodeType, KGEdgeType, KGNode, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.kg.industry_map import get_themes_for_industry, get_keywords_for_theme
from src.kg.enrichment import enrich_with_events

__all__ = [
    "KnowledgeGraphBuilder",
    "KGNodeType", "KGEdgeType", "KGNode", "KGEdge",
    "FundNode", "StockNode", "IndustryNode", "ThemeNode", "EventNode", "MacroFactorNode",
    "get_themes_for_industry", "get_keywords_for_theme",
    "enrich_with_events",
]
```

- [ ] **Step 6: Run tests to verify**

Run: `pytest tests/test_kg_schema.py tests/test_kg_graph.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/kg/ tests/test_kg_graph.py
git commit -m "feat(kg): add knowledge graph builder with query and enrichment"
```

---

### Task 4: Vector Store (Qdrant) Integration

**Files:**
- Create: `src/vectorstore/client.py`
- Create: `src/vectorstore/embedding.py`
- Create: `src/vectorstore/collections.py`
- Create: `src/vectorstore/search.py`
- Test: `tests/test_vectorstore.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_vectorstore.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from src.vectorstore.collections import COLLECTIONS, CollectionSchema
from src.vectorstore.embedding import EmbeddingPipeline


class TestCollectionDefinitions:
    def test_all_collections_have_schemas(self):
        assert "fund_news" in COLLECTIONS
        assert "fund_events" in COLLECTIONS
        assert "fund_styles" in COLLECTIONS
        assert "fund_reports" in COLLECTIONS

    def test_collection_schema_fields(self):
        schema = COLLECTIONS["fund_news"]
        assert isinstance(schema, CollectionSchema)
        assert schema.vector_size > 0
        assert len(schema.fields) >= 3
        assert "fund_code" in [f.name for f in schema.fields]
        assert "date" in [f.name for f in schema.fields]


class TestEmbeddingPipeline:
    @patch("src.vectorstore.embedding.get_embedding_client")
    def test_embed_single_text(self, mock_client):
        mock_client.return_value.embed.return_value = [0.1] * 1536
        pipeline = EmbeddingPipeline(collection="fund_news")
        vector = pipeline.embed("贵州茅台发布年报")
        assert len(vector) == 1536

    @patch("src.vectorstore.embedding.get_embedding_client")
    def test_embed_and_store(self, mock_client):
        mock_embed = MagicMock(return_value=[0.1] * 1536)
        mock_client.return_value.embed = mock_embed

        pipeline = EmbeddingPipeline(collection="fund_news")
        # Store should call upsert
        # This is a unit test — we verify the interface, not Qdrant's behavior
        items = [
            {"id": "news_001", "content": "贵州茅台年报", "fund_code": "110011", "date": "2026-05-27"}
        ]
        # Just verify it doesn't crash with mocked client
        pipeline.embed(items[0]["content"])

    def test_cosine_similarity(self):
        from src.vectorstore.search import cosine_similarity
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        vec_c = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)
        assert cosine_similarity(vec_a, vec_c) == pytest.approx(1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vectorstore.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/vectorstore/collections.py`**

```python
"""Vector store collection definitions and schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


@dataclass
class CollectionField:
    name: str
    field_type: FieldType
    index: bool = True  # Whether to create index for filtering


@dataclass
class CollectionSchema:
    name: str
    description: str
    vector_size: int = 1536  # OpenAI text-embedding-3-small
    fields: list[CollectionField] = field(default_factory=list)


COLLECTIONS: dict[str, CollectionSchema] = {
    "fund_news": CollectionSchema(
        name="fund_news",
        description="News items with embeddings for similarity search",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
            CollectionField("layer", FieldType.INTEGER),
            CollectionField("source", FieldType.STRING),
            CollectionField("relevance_score", FieldType.FLOAT),
        ],
    ),
    "fund_events": CollectionSchema(
        name="fund_events",
        description="Extracted events with embeddings for historical pattern matching",
        vector_size=1536,
        fields=[
            CollectionField("event_type", FieldType.STRING),
            CollectionField("polarity", FieldType.FLOAT),
            CollectionField("magnitude", FieldType.FLOAT),
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
        ],
    ),
    "fund_styles": CollectionSchema(
        name="fund_styles",
        description="Fund style profiles with embeddings for fundalike search",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("style", FieldType.STRING),
            CollectionField("industry", FieldType.STRING),
            CollectionField("size", FieldType.STRING),
        ],
    ),
    "fund_reports": CollectionSchema(
        name="fund_reports",
        description="Historical report chunks with embeddings for pattern matching",
        vector_size=1536,
        fields=[
            CollectionField("fund_code", FieldType.STRING),
            CollectionField("date", FieldType.STRING),
            CollectionField("score_level", FieldType.STRING),
        ],
    ),
}
```

- [ ] **Step 4: Create `src/vectorstore/embedding.py`**

```python
"""Embedding pipeline: text → vector via OpenAI-compatible API → Qdrant storage."""
from __future__ import annotations

import os
from typing import Any

from src.vectorstore.collections import COLLECTIONS


# LLM embedding configuration (same API base as existing LLM_CONFIG)
_EMBEDDING_API_BASE = os.environ.get("FUND_EMBEDDING_API_BASE", "https://opencode.ai/zen/v1")
_EMBEDDING_API_KEY = os.environ.get("FUND_EMBEDDING_API_KEY", "")
_EMBEDDING_MODEL = os.environ.get("FUND_EMBEDDING_MODEL", "text-embedding-3-small")
_EMBEDDING_DIMENSIONS = int(os.environ.get("FUND_EMBEDDING_DIMENSIONS", "1536"))


def get_embedding_client():
    """Get or create embedding client. Lazy import to avoid startup cost."""
    try:
        from openai import OpenAI
        return OpenAI(
            base_url=_EMBEDDING_API_BASE,
            api_key=_EMBEDDING_API_KEY or "unused",
        )
    except ImportError:
        raise ImportError("openai package required for embeddings: pip install openai")


class EmbeddingPipeline:
    """Embed text → upsert to Qdrant with metadata."""

    def __init__(self, collection: str, qdrant_client=None):
        self.collection_name = collection
        self.schema = COLLECTIONS.get(collection)
        self._client = qdrant_client
        self._embed_client = None

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector of dimension EMBEDDING_DIMENSIONS.
        """
        if self._embed_client is None:
            self._embed_client = get_embedding_client()
        response = self._embed_client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text,
            dimensions=_EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts into vectors.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if self._embed_client is None:
            self._embed_client = get_embedding_client()
        response = self._embed_client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=texts,
            dimensions=_EMBEDDING_DIMENSIONS,
        )
        return [item.embedding for item in response.data]

    def embed_and_store(self, items: list[dict], text_field: str = "content") -> list[str]:
        """Embed texts and upsert to Qdrant.

        Args:
            items: List of dicts with text_field and metadata.
            text_field: Key containing the text to embed.

        Returns:
            List of stored item IDs.
        """
        if self._client is None:
            raise RuntimeError("Qdrant client not configured. Set FUND_QDRANT_URL.")

        texts = [item[text_field] for item in items]
        vectors = self.embed_batch(texts)

        from qdrant_client.models import PointStruct
        points = []
        for item, vector in zip(items, vectors):
            payload = {k: v for k, v in item.items() if k != text_field}
            points.append(PointStruct(
                id=item.get("id", str(hash(item[text_field]))),
                vector=vector,
                payload=payload,
            ))

        self._client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return [p.id for p in points]

    def search(self, query: str, filters: dict | None = None, limit: int = 10) -> list[dict]:
        """Search for similar items in Qdrant.

        Args:
            query: Text to search for.
            filters: Optional metadata filters.
            limit: Maximum results to return.

        Returns:
            List of matching items with scores.
        """
        if self._client is None:
            raise RuntimeError("Qdrant client not configured. Set FUND_QDRANT_URL.")

        query_vector = self.embed(query)

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, dict) and "ne" in value:
                    # Not-equal filter not directly supported in simple MatchValue
                    continue
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
        )
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
```

- [ ] **Step 5: Create `src/vectorstore/client.py`**

```python
"""Qdrant client wrapper: collection management, initialization."""
from __future__ import annotations

import os
from typing import Any

from src.vectorstore.collections import COLLECTIONS, CollectionSchema


def get_qdrant_client():
    """Get or create Qdrant client. Defaults to local mode if no URL set."""
    from qdrant_client import QdrantClient

    url = os.environ.get("FUND_QDRANT_URL", "")
    path = os.environ.get("FUND_QDRANT_PATH", "data/qdrant_db")

    if url:
        api_key = os.environ.get("FUND_QDRANT_API_KEY", "")
        return QdrantClient(url=url, api_key=api_key)
    else:
        return QdrantClient(path=path)


def init_collections(client=None) -> list[str]:
    """Initialize all required Qdrant collections.

    Args:
        client: Optional QdrantClient instance. Created if not provided.

    Returns:
        List of created collection names.
    """
    if client is None:
        client = get_qdrant_client()

    from qdrant_client.models import Distance, VectorParams

    created = []
    for name, schema in COLLECTIONS.items():
        client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=schema.vector_size,
                distance=Distance.COSINE,
            ),
        )
        # Create payload indexes for filterable fields
        for field in schema.fields:
            if field.index:
                from qdrant_client.models import PayloadSchemaType
                client.create_payload_index(
                    collection_name=name,
                    field_name=field.name,
                    field_schema=PayloadSchemaType.KEYWORD
                    if field.field_type.value in ("string",)
                    else PayloadSchemaType.INTEGER
                    if field.field_type.value == "integer"
                    else PayloadSchemaType.FLOAT,
                )
        created.append(name)

    return created
```

- [ ] **Step 6: Create `src/vectorstore/search.py`**

```python
"""Search utilities for Qdrant: similarity search, fundalike, event matching."""
from __future__ import annotations

import math


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity in [-1, 1].
    """
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar_funds(
    fund_code: str,
    limit: int = 5,
    qdrant_client=None,
    embedding_pipeline=None,
) -> list[dict]:
    """Find funds with similar style/exposure profile.

    Args:
        fund_code: Source fund code.
        limit: Number of similar funds to return.
        qdrant_client: Optional QdrantClient instance.
        embedding_pipeline: Optional EmbeddingPipeline for fund_styles collection.

    Returns:
        List of similar funds with similarity scores.
    """
    if embedding_pipeline is None:
        from src.vectorstore.embedding import EmbeddingPipeline
        embedding_pipeline = EmbeddingPipeline(
            collection="fund_styles",
            qdrant_client=qdrant_client,
        )

    # Search for similar funds, excluding the source fund itself
    results = embedding_pipeline.search(
        query=f"fund style profile for {fund_code}",
        filters={"fund_code": {"ne": fund_code}},
        limit=limit,
    )
    return results
```

- [ ] **Step 7: Update `src/vectorstore/__init__.py`**

```python
"""Vector store module: Qdrant integration, embedding pipeline, and search."""
from src.vectorstore.collections import COLLECTIONS, CollectionSchema, CollectionField, FieldType
from src.vectorstore.embedding import EmbeddingPipeline
from src.vectorstore.client import get_qdrant_client, init_collections
from src.vectorstore.search import cosine_similarity, find_similar_funds

__all__ = [
    "COLLECTIONS", "CollectionSchema", "CollectionField", "FieldType",
    "EmbeddingPipeline",
    "get_qdrant_client", "init_collections",
    "cosine_similarity", "find_similar_funds",
]
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_vectorstore.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/vectorstore/ tests/test_vectorstore.py
git commit -m "feat(vectorstore): add Qdrant client, embedding pipeline, and collection definitions"
```

---

### Task 5: Event Taxonomy and Scoring Types

**Files:**
- Create: `src/events/taxonomy.py`
- Create: `src/events/extractor.py` (stub)
- Create: `src/analysis/scoring/types.py`
- Test: `tests/test_event_taxonomy.py`
- Test: `tests/test_scoring_types.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_event_taxonomy.py`:

```python
from src.events.taxonomy import (
    EventType, EventCategory, EVENT_HIERARCHY, get_event_type, classify_event
)


class TestEventTaxonomy:
    def test_event_types_exist(self):
        assert EventType.EARNINGS_SURPRISE.value == "earnings_surprise"
        assert EventType.RATE_CHANGE.value == "rate_change"
        assert EventType.POLICY_SHIFT.value == "policy_shift"
        assert EventType.BLACK_SWAN.value == "black_swan"

    def test_event_categories(self):
        assert EventCategory.FUNDAMENTAL.value == "fundamental"
        assert EventCategory.POLICY.value == "policy"
        assert EventCategory.MARKET.value == "market"

    def test_hierarchy_structure(self):
        # Every EventType should be in the hierarchy under a category
        all_types_in_hierarchy = []
        for category, types in EVENT_HIERARCHY.items():
            all_types_in_hierarchy.extend(types)
        for et in EventType:
            assert et in all_types_in_hierarchy, f"{et} not in hierarchy"

    def test_get_event_type(self):
        et = get_event_type("earnings_surprise")
        assert et == EventType.EARNINGS_SURPRISE

    def test_classify_event_text(self):
        result = classify_event("美联储宣布加息25个基点")
        assert result.event_type == EventType.RATE_CHANGE
        assert result.polarity < 0  # Rate hike generally negative for equity

    def test_classify_event_with_unknown_text(self):
        result = classify_event("今天天气不错")
        assert result.event_type == EventType.OTHER
```

Create `tests/test_scoring_types.py`:

```python
from src.analysis.scoring.types import ScoreComponent, MarketRegime, CompositeScore


class TestScoringTypes:
    def test_score_component_creation(self):
        sc = ScoreComponent(
            score=75.0,
            detail={"sharpe": 80, "sortino": 70},
            weights={"sharpe": 0.3, "sortino": 0.2},
            confidence=0.85,
        )
        assert sc.score == 75.0
        assert sc.confidence == 0.85

    def test_market_regime_enum(self):
        assert MarketRegime.NORMAL.value == "normal"
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert MarketRegime.TRENDING.value == "trending"
        assert MarketRegime.CRISIS.value == "crisis"

    def test_composite_score_creation(self):
        cs = CompositeScore(
            quant_score=ScoreComponent(score=80, detail={}, weights={}, confidence=0.9),
            fundamental_score=ScoreComponent(score=65, detail={}, weights={}, confidence=0.7),
            event_score=ScoreComponent(score=50, detail={}, weights={}, confidence=0.6),
            position_score=ScoreComponent(score=70, detail={}, weights={}, confidence=0.85),
            timing_score=ScoreComponent(score=55, detail={}, weights={}, confidence=0.5),
            weights_used={"quant": 0.4, "fundamental": 0.2, "event": 0.15, "position": 0.15, "timing": 0.10},
            composite=68.5,
            level="yellow",
            regime=MarketRegime.NORMAL,
        )
        assert cs.composite == 68.5
        assert cs.level == "yellow"
        assert cs.regime == MarketRegime.NORMAL

    def test_score_component_default_weights(self):
        sc = ScoreComponent(score=50, detail={}, weights={}, confidence=0.5)
        assert sc.score == 50

    def test_regime_weights_property(self):
        normal_weights = MarketRegime.NORMAL.weights()
        assert abs(sum(normal_weights.values()) - 1.0) < 0.01
        hv_weights = MarketRegime.HIGH_VOLATILITY.weights()
        assert hv_weights["event"] > normal_weights["event"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_taxonomy.py tests/test_scoring_types.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/events/taxonomy.py`**

```python
"""Event type hierarchy for news event extraction and classification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class EventCategory(Enum):
    FUNDAMENTAL = "fundamental"   # Company-level fundamentals
    POLICY = "policy"             # Government/regulatory policy
    MARKET = "market"             # Market-level events
    GEOPOLITICAL = "geopolitical"  # Geopolitical events
    COMMODITY = "commodity"        # Commodity price events
    TECHNOLOGY = "technology"      # Tech breakthrough/disruption
    MACRO = "macro"                # Macroeconomic indicators


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
    polarity: float          # -1.0 to 1.0
    magnitude: float          # 0.0 to 1.0
    time_horizon: Literal["short", "medium", "long"] = "medium"
    keywords_matched: list[str] = None

    def __post_init__(self):
        if self.keywords_matched is None:
            self.keywords_matched = []


def get_event_type(type_name: str) -> EventType:
    """Get EventType by name string."""
    for et in EventType:
        if et.value == type_name:
            return et
    return EventType.OTHER


def classify_event(text: str) -> ClassifiedEvent:
    """Rule-based event classification from text.

    Uses keyword matching to classify event type.
    LLM-based extraction is in extractor.py (Phase 2).
    """
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
    category = EventCategory.MACRO  # default
    for cat, types in EVENT_HIERARCHY.items():
        if event_type in types:
            category = cat
            break

    # Default polarity based on event type
    polarity_map = {
        EventType.EARNINGS_SURPRISE: 0.7,
        EventType.EARNINGS_MISS: -0.7,
        EventType.RATE_CHANGE: -0.3,  # Generally negative for equity
        EventType.POLICY_SHIFT: 0.0,  # Depends on context
        EventType.BLACK_SWAN: -0.9,
        EventType.TECH_BREAKTHROUGH: 0.6,
        EventType.FUND_FLOW: 0.3,
        EventType.MARKET_CRASH: -0.9,
    }
    polarity = polarity_map.get(event_type, 0.0)

    # Default magnitude
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
```

- [ ] **Step 4: Create `src/events/extractor.py` (stub)**

```python
"""Event extraction from news text. LLM-based extraction in Phase 2."""
from __future__ import annotations

from src.events.taxonomy import ClassifiedEvent, classify_event


def extract_events_from_text(text: str, use_llm: bool = False) -> list[ClassifiedEvent]:
    """Extract structured events from news text.

    Phase 1: Rule-based classification only.
    Phase 2: Will add LLM-based extraction.

    Args:
        text: News headline or content to extract events from.
        use_llm: Whether to use LLM for extraction (reserved for Phase 2).

    Returns:
        List of ClassifiedEvent objects.
    """
    # Phase 1: Rule-based only
    event = classify_event(text)
    if event.event_type.value == "other" and not text.strip():
        return []
    return [event]
```

- [ ] **Step 5: Create `src/analysis/scoring/types.py`**

```python
"""Scoring type definitions: ScoreComponent, MarketRegime, CompositeScore."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


@dataclass
class ScoreComponent:
    """A single dimension score with detail breakdown and confidence."""
    score: float          # 0-100
    detail: dict          # Sub-factor breakdown
    weights: dict[str, float]  # Dynamic weights used for this dimension
    confidence: float     # 0-1


class MarketRegime(Enum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    TRENDING = "trending"
    CRISIS = "crisis"

    def weights(self) -> dict[str, float]:
        """Return scoring dimension weights for this regime."""
        regime_weights = {
            MarketRegime.NORMAL: {
                "quant": 0.40, "fundamental": 0.20,
                "event": 0.15, "position": 0.15, "timing": 0.10,
            },
            MarketRegime.HIGH_VOLATILITY: {
                "quant": 0.25, "fundamental": 0.15,
                "event": 0.30, "position": 0.20, "timing": 0.10,
            },
            MarketRegime.TRENDING: {
                "quant": 0.35, "fundamental": 0.25,
                "event": 0.10, "position": 0.15, "timing": 0.15,
            },
            MarketRegime.CRISIS: {
                "quant": 0.15, "fundamental": 0.10,
                "event": 0.40, "position": 0.25, "timing": 0.10,
            },
        }
        return regime_weights[self]


@dataclass
class CompositeScore:
    """Composite score combining all five dimensions with regime-based weights."""
    quant_score: ScoreComponent
    fundamental_score: ScoreComponent
    event_score: ScoreComponent
    position_score: ScoreComponent
    timing_score: ScoreComponent
    weights_used: dict[str, float]
    composite: float                    # Weighted sum
    level: Literal["green", "yellow", "orange", "red"]
    regime: MarketRegime


def score_level(composite: float) -> Literal["green", "yellow", "orange", "red"]:
    """Convert composite score to level."""
    if composite >= 75:
        return "green"
    elif composite >= 50:
        return "yellow"
    elif composite >= 30:
        return "orange"
    else:
        return "red"
```

- [ ] **Step 6: Update `src/events/__init__.py`**

```python
"""Events module: taxonomy, extraction, and enrichment."""
from src.events.taxonomy import (
    EventCategory, EventType, EVENT_HIERARCHY, EVENT_KEYWORDS,
    ClassifiedEvent, get_event_type, classify_event,
)
from src.events.extractor import extract_events_from_text

__all__ = [
    "EventCategory", "EventType", "EVENT_HIERARCHY", "EVENT_KEYWORDS",
    "ClassifiedEvent", "get_event_type", "classify_event",
    "extract_events_from_text",
]
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_event_taxonomy.py tests/test_scoring_types.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/events/ src/analysis/scoring/ tests/test_event_taxonomy.py tests/test_scoring_types.py
git commit -m "feat(infra): add event taxonomy and scoring types"
```

---

### Task 6: LangGraph State and Supervisor Skeleton

**Files:**
- Create: `src/agents/state.py` (overwrite)
- Create: `src/agents/supervisor.py`
- Modify: `src/agents/__init__.py` (overwrite)
- Test: `tests/test_agents_state.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_agents_state.py`:

```python
import pytest
from src.agents.state import FundResearchState, EMPTY_STATE
from src.agents.supervisor import get_supervisor_routing, AGENT_ORDER


class TestFundResearchState:
    def test_empty_state_creation(self):
        state = EMPTY_STATE
        assert state["portfolio_config"] == {}
        assert state["funds_data"] == {}
        assert state["iteration"] == 0
        assert state["errors"] == []

    def test_state_has_all_required_fields(self):
        required_fields = [
            "portfolio_config", "report_date", "funds_data", "knowledge_graph",
            "search_plans", "raw_news", "classified_news", "scored_news",
            "research_summaries", "extracted_events",
            "market_regime", "quant_scores", "fundamental_scores",
            "event_scores", "position_scores", "timing_scores", "final_scores",
            "risk_assessments", "strategies", "portfolio_strategy",
            "iteration", "next_agent", "errors",
        ]
        for field in required_fields:
            assert field in EMPTY_STATE, f"Missing field: {field}"


class TestSupervisorRouting:
    def test_agent_order_is_valid(self):
        assert AGENT_ORDER == ["news", "quant", "risk", "research", "strategy"]

    def test_supervisor_routing_initial(self):
        routing = get_supervisor_routing(state=EMPTY_STATE)
        assert routing["next_agent"] == "news"

    def test_supervisor_routing_after_news(self):
        state = {**EMPTY_STATE, "next_agent": "quant"}
        routing = get_supervisor_routing(state=state)
        # After news, quant and risk run in parallel, then research, then strategy
        assert routing["next_agent"] in ["quant", "risk"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agents_state.py -v`
Expected: FAIL

- [ ] **Step 3: Create `src/agents/state.py`**

```python
"""LangGraph state definition: shared state across all agents."""
from __future__ import annotations

from typing import TypedDict


class FundResearchState(TypedDict, total=False):
    """Shared state across all LangGraph agents.

    Used as the state schema for the supervisor graph.
    All fields are optional (total=False) to allow partial updates.
    """
    # Input
    portfolio_config: dict
    report_date: str

    # Data layer (populated by tools)
    funds_data: dict              # Per-fund raw data
    knowledge_graph: dict         # KG snapshot (serializable dict, not nx.Graph)
                                   # Keys: {nodes: [...], edges: [...], exposures: {fund_code: {...}}}

    # News pipeline results
    search_plans: dict            # Per-fund SearchPlan
    raw_news: dict                # Per-fund raw news pool
    classified_news: dict         # Per-fund classified news
    scored_news: dict             # Per-fund scored+reranked news
    research_summaries: dict      # Per-fund research-style summaries
    extracted_events: dict        # Per-fund extracted events

    # Scoring results
    market_regime: str            # Detected regime
    quant_scores: dict            # Per-fund QuantScore
    fundamental_scores: dict      # Per-fund FundamentalScore
    event_scores: dict            # Per-fund EventScore
    position_scores: dict         # Per-fund PositionScore
    timing_scores: dict           # Per-fund TimingScore
    final_scores: dict            # Per-fund composite scores

    # Strategy results
    risk_assessments: dict        # Per-fund risk assessment
    strategies: dict              # Per-fund StrategyAdvice
    portfolio_strategy: dict      # Portfolio-level strategy

    # Orchestration
    iteration: int
    next_agent: str
    errors: list[str]


# Empty state template for initialization
EMPTY_STATE: FundResearchState = {
    "portfolio_config": {},
    "report_date": "",
    "funds_data": {},
    "knowledge_graph": {},
    "search_plans": {},
    "raw_news": {},
    "classified_news": {},
    "scored_news": {},
    "research_summaries": {},
    "extracted_events": {},
    "market_regime": "normal",
    "quant_scores": {},
    "fundamental_scores": {},
    "event_scores": {},
    "position_scores": {},
    "timing_scores": {},
    "final_scores": {},
    "risk_assessments": {},
    "strategies": {},
    "portfolio_strategy": {},
    "iteration": 0,
    "next_agent": "",
    "errors": [],
}
```

- [ ] **Step 4: Create `src/agents/supervisor.py`**

```python
"""Supervisor agent: routes tasks to specialized agents based on state."""
from __future__ import annotations

from src.agents.state import FundResearchState

# Agent execution order: news first, then quant/risk parallel, then research, then strategy
AGENT_ORDER = ["news", "quant", "risk", "research", "strategy"]


# Which agents can run in parallel
PARALLEL_GROUPS = [
    {"quant", "risk"},  # quant and risk can run simultaneously
]


def get_supervisor_routing(state: FundResearchState) -> dict:
    """Determine which agent should run next based on current state.

    The supervisor follows a fixed order optimized for data dependencies:
    1. NEWS: Collect and process news (needed by all other agents)
    2. QUANT + RISK: Compute quantitative and risk scores (parallel)
    3. RESEARCH: AI-driven analysis (needs scores + events)
    4. STRATEGY: Synthesize final strategy (needs all results)

    Args:
        state: Current research state.

    Returns:
        Dict with next_agent name and routing reason.
    """
    next_agent = state.get("next_agent", "")

    # If state specifies next agent, follow it
    if next_agent and next_agent in AGENT_ORDER:
        return {"next_agent": next_agent, "reason": f"Scheduled: {next_agent}"}

    # Determine which agents have completed their work
    has_news = bool(state.get("scored_news"))
    has_quant = bool(state.get("quant_scores"))
    has_risk = bool(state.get("risk_assessments"))
    has_research = bool(state.get("fundamental_scores") and state.get("timing_scores"))
    has_strategy = bool(state.get("strategies"))

    # Route based on completion status
    if not has_news:
        return {"next_agent": "news", "reason": "News collection needed first"}
    elif not has_quant:
        return {"next_agent": "quant", "reason": "Quantitative scoring needed"}
    elif not has_risk:
        return {"next_agent": "risk", "reason": "Risk assessment needed"}
    elif not has_research:
        return {"next_agent": "research", "reason": "Fundamental analysis needed (depends on scores + events)"}
    elif not has_strategy:
        return {"next_agent": "strategy", "reason": "Strategy synthesis needed (depends on all results)"}
    else:
        return {"next_agent": "done", "reason": "All agents completed"}
```

- [ ] **Step 5: Update `src/agents/__init__.py`**

```python
"""Multi-agent system: LangGraph supervisor with specialized research agents."""
from src.agents.state import FundResearchState, EMPTY_STATE
from src.agents.supervisor import get_supervisor_routing, AGENT_ORDER

__all__ = [
    "FundResearchState", "EMPTY_STATE",
    "get_supervisor_routing", "AGENT_ORDER",
]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_agents_state.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/agents/ tests/test_agents_state.py
git commit -m "feat(agents): add LangGraph state definition and supervisor routing"
```

---

### Task 7: Integration Verification

**Goal:** Verify that all Phase 1 modules work together and existing functionality is not broken.

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests pass + all new Phase 1 tests pass

- [ ] **Step 2: Verify CLI still works**

Run: `python -m src.cli --help`
Expected: CLI help output shown (no import errors)

- [ ] **Step 3: Verify new module imports**

Run: `python -c "from src.kg import KnowledgeGraphBuilder; from src.vectorstore import EmbeddingPipeline; from src.events import EventType, classify_event; from src.analysis.scoring.types import ScoreComponent, MarketRegime; from src.agents import FundResearchState; print('All imports OK')"`

Expected: "All imports OK"

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fixup(phase1): integration verification fixes"
```