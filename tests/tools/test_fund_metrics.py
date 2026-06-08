"""Pure fund metric tool tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.tools.fund.metrics import (
    calculate_fund_metrics,
    calculate_returns_from_nav,
    normalize_nav_history,
)


def test_nav_returns_volatility_and_drawdown_are_deterministic():
    nav = [
        {"date": "2026-01-01", "nav": 1.0},
        {"date": "2026-01-02", "nav": 1.1},
        {"date": "2026-01-03", "nav": 1.0},
        {"date": "2026-01-04", "nav": 1.2},
    ]

    returns = calculate_returns_from_nav(nav)
    metrics = calculate_fund_metrics(nav)

    assert returns == pytest.approx([0.1, -0.090909, 0.2], rel=1e-5)
    assert metrics["total_return"] == pytest.approx(0.2)
    assert metrics["max_drawdown"] == pytest.approx(0.090909)
    assert metrics["annualized_volatility"] > 0
    assert metrics == calculate_fund_metrics(nav)


def test_empty_nav_is_handled_safely():
    assert normalize_nav_history([]) == []
    assert calculate_returns_from_nav([]) == []

    metrics = calculate_fund_metrics([])

    assert metrics["observation_count"] == 0
    assert metrics["total_return"] == 0.0
    assert metrics["annualized_volatility"] == 0.0
    assert metrics["max_drawdown"] == 0.0
    assert metrics["sharpe"] == 0.0
    assert metrics["sortino"] == 0.0


def test_fund_metric_tools_have_no_network_or_io_imports():
    imports = _imports_from(Path("src/tools/fund/metrics.py"))
    forbidden = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "pathlib",
        "openai",
        "anthropic",
        "langchain",
    }

    assert not (imports & forbidden)


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports
