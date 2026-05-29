"""Evidence builder functions — wrappers around EvidenceItem factories and EvidenceGraph methods.

Provides three builder functions:
- build_hard_evidence:  Pure computation tool output → HardEvidence (confidence_weight always 1.0)
- build_soft_evidence:  News/sentiment source → SoftEvidence (confidence clamped to [0.1, 0.9])
- build_hybrid_evidence: Multiple SoftEvidence items → HybridEvidence via graph upgrade
"""

from __future__ import annotations

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
