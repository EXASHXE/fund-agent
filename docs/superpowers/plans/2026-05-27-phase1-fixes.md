# Phase 1 Fix Plan: KG NetworkX Pattern & Import Errors

## Problem Summary

All 26 test files fail with `ModuleNotFoundError: No module named 'src'` because there's no `conftest.py` setting up `sys.path`. Additionally, the KG module has a broken design: `schema.py` uses `frozen=True` dataclasses while `graph.py` and `enrichment.py` mix object-as-node and string-ID-as-node patterns in NetworkX.

## Root Causes

1. **No conftest.py** → pytest can't import `src.*` modules
2. **`src/kg/__init__.py`** imports `KGNode` which doesn't exist in `schema.py`
3. **`src/kg/schema.py`** uses `frozen=True` with `tuple[str, ...]` for keywords — but the real issue is that NetworkX node representation needs a consistent pattern
4. **`src/kg/graph.py`** mixes `G.add_node(fund_node)` (object) and `G.has_node(industry_node.id)` (string ID)
5. **`src/kg/enrichment.py`** mixes `graph.add_node(event)` (object) and `graph.has_node(entity_id)` (string ID)

## Design Decision

**Use string IDs as NetworkX nodes, store dataclass instances as `G.nodes[node_id]["data"]` attributes.**

This is the standard NetworkX pattern:
- `G.add_node("fund:110011", data=fund_node)` — not `G.add_node(fund_node)`
- `G.has_node("fund:110011")` — consistent string-based lookup
- `G.nodes["fund:110011"]["data"]` — retrieve dataclass instance
- `G.add_edge("fund:110011", "stock:600519", edge_data=edge)` — string IDs for edges

This means dataclasses should be **mutable** (remove `frozen=True`, unfreeze `ThemeNode.keywords` back to `list[str]`).

## Task Breakdown

### Task A: Fix `conftest.py` (trivial)
- Create `conftest.py` at project root with `sys.path.insert(0, os.path.dirname(__file__))`

### Task B: Fix `src/kg/schema.py`
- Remove `frozen=True` from all node dataclasses (FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode)
- Change `ThemeNode.keywords` from `tuple[str, ...] = ()` to `list[str] = field(default_factory=list)`
- Remove `eq=True` from frozen decorator (let dataclasses use default equality)
- Remove unused `from typing import Literal` import
- Keep `KGEdge` as regular mutable dataclass (it already is)

### Task C: Fix `src/kg/__init__.py`
- Remove `KGNode` from both the `from ... import` line and the `__all__` list

### Task D: Fix `src/kg/graph.py`
- Change ALL `G.add_node(node_obj)` to `G.add_node(node_obj.id, data=node_obj)`
- Verify ALL `G.has_node(...)` calls use string IDs consistently (they mostly do already)
- Verify ALL `G.add_edge(...)` calls use string IDs (they already use `.id` properties)
- No other logic changes needed

### Task E: Fix `src/kg/enrichment.py`
- Change `graph.add_node(event)` to `graph.add_node(event.id, data=event)`
- Change `graph.has_node(entity_id)` — already uses string ID, OK
- Change `graph.add_edge(event.id, ...)` — already uses string ID, OK
- Remove the inline `from src.kg.schema import KGEdge` (move to top-level import)

### Task F: Fix `tests/test_kg_schema.py`
- Remove `KGNode` from import line
- Remove `test_kg_node_hash_and_equality` test (was testing frozen dataclass hash)
- Remove `test_kg_node_inequality` test (same reason)
- Keep all other tests — mutable dataclasses still support `==` comparison by default

### Task G: Fix `tests/test_kg_graph.py`
- Remove `FundNode` and `StockNode` imports (no longer needed for isinstance checks)
- Change `isinstance(n, FundNode)` / `isinstance(n, StockNode)` checks to use string ID pattern:
  - Count stock nodes: `sum(1 for n in graph.nodes if n.startswith("stock:"))`
  - Count industry nodes: `sum(1 for n in graph.nodes if n.startswith("industry:"))`
  - Count event nodes: `sum(1 for n in graph.nodes if n.startswith("event:"))`
- Change `len(stock_nodes) == 3` assertions accordingly

## Verification

After all fixes:
1. `PYTHONPATH=. python -m pytest tests/test_kg_schema.py tests/test_kg_graph.py tests/test_vectorstore.py tests/test_event_taxonomy.py tests/test_agents_state.py -v` — all Phase 1 tests pass
2. `PYTHONPATH=. python -m pytest tests/ -v` — all existing tests pass
3. `PYTHONPATH=. python -c "from src.kg import KnowledgeGraphBuilder, FundNode, ThemeNode; print('KG import OK')"`
4. `PYTHONPATH=. python -c "from src.events import classify_event; print('Events import OK')"`