"""Evidence builder contract tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.tools.evidence.builders import (
    build_hard_evidence_from_metric,
    build_soft_evidence_from_mcp_result,
)


def test_metric_result_builds_hard_evidence_confidence_one():
    item = build_hard_evidence_from_metric(
        metric_name="local_quant_tools",
        metric_value={"sharpe": 1.2},
        claim="Risk metric computed",
        related_entities=["fund:110011"],
    )

    assert item.evidence_type == "HardEvidence"
    assert item.confidence_weight == 1.0


def test_soft_evidence_builder_requires_source_type():
    with pytest.raises(ValueError, match="source_type"):
        _soft(source_type="")


def test_soft_evidence_builder_requires_timestamp():
    with pytest.raises(ValueError, match="timestamp"):
        _soft(timestamp="")


def test_soft_evidence_builder_requires_related_entities():
    with pytest.raises(ValueError, match="related_entities"):
        _soft(related_entities=[])


def test_evidence_builders_are_json_serializable():
    item = _soft()

    json.dumps(item.to_dict())


def test_evidence_builders_do_not_import_network_or_llm():
    imports = _imports_from(Path("src/tools/evidence/builders.py"))
    forbidden = {"requests", "httpx", "aiohttp", "socket", "openai", "anthropic", "langchain"}

    assert not (imports & forbidden)


def _soft(
    source_type: str = "financial_news",
    timestamp: str = "2026-05-30T00:00:00",
    related_entities: list[str] | None = None,
):
    return build_soft_evidence_from_mcp_result(
        source_type=source_type,
        timestamp=timestamp,
        related_entities=related_entities if related_entities is not None else ["fund:110011"],
        claim="News event detected",
        value={"title": "event"},
    )


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports
