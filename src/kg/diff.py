"""Graph diff: structural diff between two knowledge graphs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraphDiff:
    """Structural diff between two knowledge graphs.

    Attributes:
        added_nodes: Node IDs present in ``new_graph`` but not in ``old_graph``.
        removed_nodes: Node IDs present in ``old_graph`` but not in ``new_graph``.
        modified_nodes: Node IDs present in both graphs whose ``data`` dict differs.
        added_edges: ``(source, target)`` tuples present in ``new_graph`` only.
        removed_edges: ``(source, target)`` tuples present in ``old_graph`` only.
    """
    added_nodes: list[str]
    removed_nodes: list[str]
    modified_nodes: list[str]
    added_edges: list[tuple]
    removed_edges: list[tuple]

    def is_empty(self) -> bool:
        """Return ``True`` if no differences were detected."""
        return (
            not self.added_nodes
            and not self.removed_nodes
            and not self.modified_nodes
            and not self.added_edges
            and not self.removed_edges
        )

    def summary(self) -> str:
        """Return a human-readable summary of the diff."""
        parts = []
        if self.added_nodes:
            parts.append(f"+{len(self.added_nodes)} nodes")
        if self.removed_nodes:
            parts.append(f"-{len(self.removed_nodes)} nodes")
        if self.modified_nodes:
            parts.append(f"~{len(self.modified_nodes)} nodes")
        if self.added_edges:
            parts.append(f"+{len(self.added_edges)} edges")
        if self.removed_edges:
            parts.append(f"-{len(self.removed_edges)} edges")
        return ", ".join(parts) if parts else "no changes"
