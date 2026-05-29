"""Knowledge graph enrichment: add events and update impact edges."""
from __future__ import annotations

import networkx as nx

from src.graph.schema import KGEdge, KGEdgeType, EventNode


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
        graph.add_node(event.id, data=event)

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