"""EvidenceGraph — unified evidence store with dedup, conflict detection, and hybrid upgrades.

Merges HardEvidence (pure math, confidence=1.0) and SoftEvidence (news/sentiment,
confidence 0.1-0.9) into a single queryable graph. Supports:

- Deduplication by claim similarity + entity overlap
- Conflict detection (opposite direction on shared entities)
- SoftEvidence → HybridEvidence upgrade when 2+ sources corroborate
- Entity-level confidence aggregation
- Validation and serialization

Downstream consumers (Phase 6 Planner/Critic) use EvidenceGraph for research
and auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.schemas.evidence import EvidenceItem, EvidenceType


@dataclass
class EvidenceGraph:
    """Unified evidence store backed by a dict of EvidenceItem instances.

    Attributes:
        items: Mapping of evidence_id -> EvidenceItem.
        edges: List of (from_id, to_id) tuples representing relationships
               (supports / contradicts) between evidence items.
    """

    items: dict[str, EvidenceItem] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    # ── Core CRUD ────────────────────────────────────────────────────────

    def add(self, item: EvidenceItem) -> str:
        """Add an evidence item to the graph.

        Deduplication-by-ID: if an item with the same evidence_id already
        exists it is silently overwritten.

        Returns:
            The evidence_id of the added item.
        """
        self.items[item.evidence_id] = item
        return item.evidence_id

    def get(self, evidence_id: str) -> EvidenceItem | None:
        """Retrieve an evidence item by its ID, or None if absent."""
        return self.items.get(evidence_id)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Link two evidence items (supports / contradicts relationship).

        No validation is performed on whether the IDs exist in the graph;
        callers should ensure IDs are present.
        """
        self.edges.append((from_id, to_id))

    # ── Hybrid upgrade ───────────────────────────────────────────────────

    def upgrade_to_hybrid(
        self, soft_id: str, supporting_ids: list[str]
    ) -> EvidenceItem | None:
        """Upgrade a SoftEvidence item to HybridEvidence.

        Conditions:
        - The target item must exist and have evidence_type == "SoftEvidence".
        - At least 2 supporting evidence IDs must be provided.
        - All supporting IDs must exist in the graph.

        Effects:
        - evidence_type is changed to "HybridEvidence".
        - confidence_weight is boosted by 30% (capped at 0.95).

        Returns:
            The updated EvidenceItem, or None if the upgrade cannot be performed.
        """
        item = self.items.get(soft_id)
        if not item or item.evidence_type != "SoftEvidence":
            return None
        if len(supporting_ids) < 2:
            return None
        # Verify all supporting items exist
        for sid in supporting_ids:
            if sid not in self.items:
                return None
        # Perform the upgrade
        item.evidence_type = "HybridEvidence"
        item.confidence_weight = min(item.confidence_weight * 1.3, 0.95)
        return item

    # ── Deduplication ────────────────────────────────────────────────────

    def deduplicate(self) -> list[str]:
        """Find and remove near-duplicate claims.

        Two items are considered duplicates when:
        - They share the exact same set of related_entities.
        - Their claim similarity (word overlap) is > 0.85.

        The item with the *lower* confidence_weight is removed. If confidence
        weights are equal, the item appearing later in iteration is removed.

        Returns:
            List of evidence_ids that were removed.
        """
        removed: list[str] = []
        ids = list(self.items.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a, id_b = ids[i], ids[j]
                if id_a in removed or id_b in removed:
                    continue

                item_a = self.items[id_a]
                item_b = self.items[id_b]

                if set(item_a.related_entities) == set(item_b.related_entities):
                    similarity = self._claim_similarity(item_a.claim, item_b.claim)
                    if similarity > 0.85:
                        if item_a.confidence_weight >= item_b.confidence_weight:
                            del self.items[id_b]
                            removed.append(id_b)
                        else:
                            del self.items[id_a]
                            removed.append(id_a)
        return removed

    # ── Conflict detection ───────────────────────────────────────────────

    def detect_conflicts(self) -> list[tuple[str, str]]:
        """Find evidence pairs with opposite direction for shared entities.

        A conflict exists when two evidence items share at least one entity
        and have opposite directions (one "positive", the other "negative").
        Neutral items do not conflict with anything.

        Returns:
            List of (evidence_id_a, evidence_id_b) tuples for conflicting pairs.
        """
        conflicts: list[tuple[str, str]] = []
        ids = list(self.items.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a, id_b = ids[i], ids[j]
                item_a = self.items[id_a]
                item_b = self.items[id_b]

                shared = set(item_a.related_entities) & set(item_b.related_entities)
                if not shared:
                    continue

                if (item_a.direction == "positive" and item_b.direction == "negative") or (
                    item_a.direction == "negative" and item_b.direction == "positive"
                ):
                    conflicts.append((id_a, id_b))

        return conflicts

    # ── Claim similarity (internal) ──────────────────────────────────────

    @staticmethod
    def _claim_similarity(claim_a: str, claim_b: str) -> float:
        """Compute simple word-overlap similarity between two claim strings.

        Uses intersection-over-min(|A|, |B|) on lowercased word sets.
        Returns 0.0 if either claim is empty.
        """
        if not claim_a or not claim_b:
            return 0.0
        words_a = set(claim_a.lower().split())
        words_b = set(claim_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        return len(intersection) / min(len(words_a), len(words_b))

    # ── Aggregation ──────────────────────────────────────────────────────

    def aggregate_confidence(self, entity: str) -> float:
        """Compute the weighted-average confidence across all evidence for an entity.

        Each item contributes equally (weight = 1) for simplicity.
        Returns 0.0 when no evidence exists for the entity.
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for item in self.items.values():
            if entity in item.related_entities:
                weighted_sum += item.confidence_weight * 1.0
                total_weight += 1.0
        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    # ── Filtering ────────────────────────────────────────────────────────

    def by_entity(self, entity: str) -> list[EvidenceItem]:
        """Return all evidence items related to a given entity."""
        return [item for item in self.items.values() if entity in item.related_entities]

    def by_type(self, etype: EvidenceType) -> list[EvidenceItem]:
        """Return all evidence items of a specific evidence type."""
        return [item for item in self.items.values() if item.evidence_type == etype]

    # ── Count helpers ────────────────────────────────────────────────────

    def hard_evidence_count(self) -> int:
        """Number of HardEvidence items in the graph."""
        return len(self.by_type("HardEvidence"))

    def soft_evidence_count(self) -> int:
        """Number of SoftEvidence items in the graph."""
        return len(self.by_type("SoftEvidence"))

    def hybrid_evidence_count(self) -> int:
        """Number of HybridEvidence items in the graph."""
        return len(self.by_type("HybridEvidence"))

    # ── Validation ───────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Validate the entire graph's integrity.

        Checks:
        - HardEvidence items must have confidence_weight == 1.0
        - All items must have confidence_weight in [0.0, 1.0]

        Returns:
            List of human-readable issue strings (empty = no issues).
        """
        issues: list[str] = []
        for item in self.items.values():
            if item.evidence_type == "HardEvidence" and item.confidence_weight != 1.0:
                issues.append(
                    f"HardEvidence {item.evidence_id}: confidence must be 1.0, "
                    f"got {item.confidence_weight}"
                )
            if item.confidence_weight < 0.0 or item.confidence_weight > 1.0:
                issues.append(
                    f"Evidence {item.evidence_id}: invalid confidence "
                    f"{item.confidence_weight}"
                )
        return issues

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a JSON-compatible dictionary.

        Each item is serialized via EvidenceItem.to_dict().
        A ``stats`` sub-dictionary provides summary counts.
        """
        return {
            "items": {eid: item.to_dict() for eid, item in self.items.items()},
            "edges": self.edges,
            "stats": {
                "total": len(self.items),
                "hard": self.hard_evidence_count(),
                "soft": self.soft_evidence_count(),
                "hybrid": self.hybrid_evidence_count(),
                "conflicts": len(self.detect_conflicts()),
            },
        }
