"""Evidence builder functions — wrappers around EvidenceItem factories and EvidenceGraph methods.

Provides three builder functions:
- build_hard_evidence:  Pure computation tool output → HardEvidence (confidence_weight always 1.0)
- build_soft_evidence:  News/sentiment source → SoftEvidence (confidence clamped to [0.1, 0.9])
- build_hybrid_evidence: Multiple SoftEvidence items → HybridEvidence via graph upgrade
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


def build_hard_evidence(
    tool_name: str,
    output: dict,
    claim: str,
    entities: list[str],
    direction: str = "neutral",
    provenance: dict | None = None,
) -> EvidenceItem:
    """Create HardEvidence from a pure tool output. confidence_weight is always 1.0.

    Args:
        tool_name: Name of the computation tool (e.g. "sortino_tool", "xirr_calculator").
        output: Computed value from the tool.
        claim: Human-readable claim about what was computed.
        entities: Related fund/stock/industry identifiers.
        direction: positive, negative, or neutral.
        provenance: Optional provenance metadata.

    Returns:
        EvidenceItem with evidence_type="HardEvidence" and confidence_weight=1.0.
    """
    return EvidenceItem.from_tool_output(
        tool_name=tool_name,
        output=output,
        claim=claim,
        entities=entities,
        direction=direction,
        provenance=provenance or {},
    )


def build_soft_evidence(
    source: str,
    claim: str,
    entities: list[str],
    direction: str = "neutral",
    confidence: float = 0.5,
) -> EvidenceItem:
    """Create SoftEvidence from news/sentiment. confidence clamped to [0.1, 0.9].

    Args:
        source: Source name (e.g. "finnhub", "tavily", "akshare").
        claim: The evidence claim string.
        entities: Related fund/stock/industry identifiers.
        direction: positive, negative, or neutral.
        confidence: Confidence value, clamped to [0.1, 0.9].

    Returns:
        EvidenceItem with evidence_type="SoftEvidence" and clamped confidence_weight.
    """
    return EvidenceItem.from_news(
        source=source,
        news_item={"claim": claim},
        entities=entities,
        direction=direction,
        confidence=confidence,
    )


def build_hybrid_evidence(soft_items: list[EvidenceItem]) -> EvidenceItem | None:
    """Upgrade SoftEvidence items to HybridEvidence via multi-source corroboration.

    Requires at least 2 SoftEvidence items. The first item is upgraded using
    the remaining items as supporting evidence. If fewer than 2 items are provided,
    returns the single item unchanged (or None if the list is empty).

    Args:
        soft_items: List of SoftEvidence items to corroborate.

    Returns:
        Upgraded HybridEvidence item, single item fallback, or None.
    """
    if not soft_items:
        return None
    if len(soft_items) < 2:
        return soft_items[0]

    graph = EvidenceGraph()
    for item in soft_items:
        graph.add(item)

    supporting_ids = [item.evidence_id for item in soft_items[1:]]
    result = graph.upgrade_to_hybrid(soft_items[0].evidence_id, supporting_ids)
    if result is not None:
        return result

    return soft_items[0]  # fallback to original


def build_hard_evidence_from_metric(
    *,
    metric_name: str,
    metric_value: Any,
    claim: str,
    related_entities: list[str],
    direction: str = "neutral",
    provenance: dict | None = None,
) -> EvidenceItem:
    """Build HardEvidence from a local metric result."""
    if not related_entities:
        raise ValueError("related_entities is required for HardEvidence")
    return EvidenceItem.from_tool_output(
        tool_name=metric_name,
        output=metric_value,
        claim=claim,
        entities=related_entities,
        direction=direction,
        provenance=provenance or {"builder": "build_hard_evidence_from_metric"},
    )


def build_soft_evidence_from_mcp_result(
    *,
    source_type: str,
    timestamp: datetime | str,
    related_entities: list[str],
    claim: str,
    value: Any,
    confidence_weight: float = 0.5,
    direction: str = "neutral",
    provenance: dict | None = None,
) -> EvidenceItem:
    """Build SoftEvidence from a structured MCP result."""
    if not source_type:
        raise ValueError("source_type is required for SoftEvidence")
    if not timestamp:
        raise ValueError("timestamp is required for SoftEvidence")
    if not related_entities:
        raise ValueError("related_entities is required for SoftEvidence")

    parsed_timestamp = _parse_timestamp(timestamp)
    return EvidenceItem(
        evidence_id=_new_evidence_id(),
        evidence_type="SoftEvidence",
        source_type=source_type,
        timestamp=parsed_timestamp,
        related_entities=related_entities,
        claim=claim,
        value=value,
        confidence_weight=min(max(confidence_weight, 0.1), 0.9),
        direction=direction,
        provenance=provenance or {"builder": "build_soft_evidence_from_mcp_result"},
    )


def build_soft_evidence_from_sentiment(
    *,
    source_type: str,
    timestamp: datetime | str,
    related_entities: list[str],
    sentiment_score: float,
    claim: str,
    direction: str | None = None,
    provenance: dict | None = None,
) -> EvidenceItem:
    """Build SoftEvidence from a structured sentiment result."""
    if direction is None:
        if sentiment_score > 0.05:
            direction = "positive"
        elif sentiment_score < -0.05:
            direction = "negative"
        else:
            direction = "neutral"
    return build_soft_evidence_from_mcp_result(
        source_type=source_type,
        timestamp=timestamp,
        related_entities=related_entities,
        claim=claim,
        value={"sentiment_score": sentiment_score},
        confidence_weight=min(max(abs(sentiment_score), 0.1), 0.9),
        direction=direction,
        provenance=provenance or {"builder": "build_soft_evidence_from_sentiment"},
    )


def build_hybrid_evidence_from_supporting_items(
    supporting_items: list[EvidenceItem],
) -> EvidenceItem | None:
    """Build HybridEvidence from multiple supporting evidence items."""
    return build_hybrid_evidence(supporting_items)


def _parse_timestamp(timestamp: datetime | str) -> datetime:
    if isinstance(timestamp, datetime):
        return timestamp
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"timestamp must be ISO-8601 compatible: {timestamp}") from exc


def _new_evidence_id() -> str:
    import uuid

    return str(uuid.uuid4())
