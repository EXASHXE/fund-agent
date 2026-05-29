"""Evidence-contract.v2 typed dataclass and factory methods.

Replaces dict-based evidence construction with a validated dataclass.
Old code in src/core/contracts.py continues to produce dicts unchanged.
New code uses EvidenceItem and its factory methods for type safety.

Constraints:
- HardEvidence.confidence_weight MUST be 1.0 (enforced at construction)
- HardEvidence can only come from pure computation tools (from_tool_output)
- SoftEvidence can only come from news/sentiment sources (from_news)
- Missing source_type, timestamp, or empty related_entities → validation error
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

EvidenceType = Literal["HardEvidence", "SoftEvidence", "HybridEvidence"]
Direction = Literal["positive", "negative", "neutral"]
SourceType = Literal[
    "quant_tool", "news_source", "sentiment_analysis",
    "kg_query", "llm_inference", "hybrid",
]


@dataclass
class EvidenceItem:
    """Typed evidence contract (evidence-contract.v2).

    Attributes:
        evidence_id: Unique identifier for this evidence item.
        evidence_type: HardEvidence (pure computation), SoftEvidence (news/sentiment),
                       or HybridEvidence (combined).
        source_type: Name of the tool, service, or pipeline that produced this evidence.
        timestamp: When this evidence was generated.
        related_entities: Fund codes, stock codes, or industry names this evidence
                          pertains to. Must not be empty.
        claim: Human-readable claim statement.
        value: The actual evidence payload (numeric, dict, list, etc.).
        confidence_weight: Confidence in [0.0, 1.0]. HardEvidence must be exactly 1.0.
                           SoftEvidence defaults to 0.5, clamped to [0.1, 0.9].
        direction: positive, negative, or neutral.
        version: Schema version string. Defaults to "evidence-contract.v2".
        provenance: Arbitrary dict tracing source of this evidence.
    """

    evidence_id: str
    evidence_type: EvidenceType
    source_type: str
    timestamp: datetime
    related_entities: list[str]
    claim: str
    value: Any
    confidence_weight: float = 1.0
    direction: Direction = "neutral"
    version: str = "evidence-contract.v2"
    provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate constraints after initialization."""
        # HardEvidence must have confidence_weight == 1.0
        if self.evidence_type == "HardEvidence" and self.confidence_weight != 1.0:
            raise ValueError(
                f"HardEvidence confidence_weight must be 1.0, got {self.confidence_weight}"
            )

        # Validate required fields
        if not self.source_type:
            raise ValueError("EvidenceItem.source_type cannot be empty")

        if not self.related_entities:
            raise ValueError("EvidenceItem.related_entities cannot be empty")

        # Validate confidence_weight range
        if self.confidence_weight < 0.0 or self.confidence_weight > 1.0:
            raise ValueError(
                f"confidence_weight must be in [0.0, 1.0], "
                f"got {self.confidence_weight}"
            )

    @staticmethod
    def from_tool_output(
        tool_name: str,
        output: Any,
        claim: str,
        entities: list[str],
        direction: Direction = "neutral",
        provenance: dict | None = None,
    ) -> EvidenceItem:
        """Factory: Create HardEvidence from a pure computation tool.

        Args:
            tool_name: Name of the tool (e.g. "sortino_tool", "xirr_calculator").
            output: Computed value from the tool.
            claim: Human-readable claim about what was computed.
            entities: Related fund/stock/industry identifiers.
            direction: positive, negative, or neutral.
            provenance: Optional provenance metadata.

        Returns:
            EvidenceItem with evidence_type="HardEvidence" and
            confidence_weight=1.0.
        """
        import uuid

        return EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            evidence_type="HardEvidence",
            source_type=tool_name,
            timestamp=datetime.now(),
            related_entities=entities,
            claim=claim,
            value=output,
            confidence_weight=1.0,  # HardEvidence always 1.0
            direction=direction,
            provenance=provenance or {},
        )

    @staticmethod
    def from_news(
        source: str,
        news_item: dict,
        entities: list[str],
        direction: Direction = "neutral",
        confidence: float = 0.5,
    ) -> EvidenceItem:
        """Factory: Create SoftEvidence from a news or sentiment source.

        Args:
            source: Source name (e.g. "finnhub", "tavily", "akshare").
            news_item: Dict with at minimum a "title" or "claim" key.
            entities: Related fund/stock/industry identifiers.
            direction: positive, negative, or neutral.
            confidence: Confidence value. Clamped to [0.1, 0.9].

        Returns:
            EvidenceItem with evidence_type="SoftEvidence" and
            confidence_weight clamped to [0.1, 0.9].
        """
        import uuid

        return EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            evidence_type="SoftEvidence",
            source_type=source,
            timestamp=datetime.now(),
            related_entities=entities,
            claim=news_item.get("title", news_item.get("claim", "")),
            value=news_item,
            confidence_weight=min(max(confidence, 0.1), 0.9),
            direction=direction,
            provenance={"source": source},
        )

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict.

        Compatible with the existing evidence JSON format used by
        src/core/contracts.py.
        """
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["evidence_type"] = self.evidence_type
        return result
