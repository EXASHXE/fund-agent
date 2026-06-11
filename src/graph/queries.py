"""Knowledge Graph query functions — typed query interface from plan.txt spec."""
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.schema import KGEdgeType


def get_entity_chain(kg: KnowledgeGraph, fund_code: str, depth: int = 3) -> dict:
    """Get fund→stock→industry→theme chain. Default depth 3."""
    if kg.graph is None:
        return {"fund": fund_code, "chain": []}
    return kg._builder.entity_chain(kg.graph, fund_code)


def query_exposure(kg: KnowledgeGraph, fund_code: str) -> dict:
    """Get industry/theme exposure for a fund."""
    if kg.graph is None:
        return {"fund": fund_code, "exposure": {}}
    return kg._builder.get_fund_exposure(kg.graph, fund_code)


def expand_theme(kg: KnowledgeGraph, theme_name: str, depth: int = 2) -> dict:
    """Expand theme to find related industries/stocks/funds. Default depth 2, max 3."""
    if kg.graph is None:
        return {"theme": theme_name, "expansion": {}}
    max_d = min(depth, 3)
    return kg._builder.theme_diffusion(kg.graph, theme_name, max_d)


def find_related_events(kg: KnowledgeGraph, entity_id: str) -> list:
    """Find events related to an entity (fund or stock)."""
    if kg.graph is None:
        return []

    if entity_id.startswith("fund:"):
        related = []
        fund_id = entity_id
        if kg.graph.has_node(fund_id):
            for _, stock_dst, data in kg.graph.edges(fund_id, data=True):
                edge = data.get("edge_data")
                if edge and edge.edge_type == KGEdgeType.HOLDS:
                    for event_src, _, ev_data in kg.graph.in_edges(stock_dst, data=True):
                        ev_edge = ev_data.get("edge_data")
                        if ev_edge and ev_edge.edge_type == KGEdgeType.IMPACTS:
                            event_node = kg.graph.nodes[event_src].get("data")
                            if event_node:
                                related.append({
                                    "event_id": event_node.event_id,
                                    "event_type": event_node.event_type,
                                    "subtype": event_node.subtype,
                                    "polarity": ev_edge.polarity,
                                    "magnitude": ev_edge.magnitude,
                                })
        return related

    if entity_id.startswith("stock:"):
        stock_id = entity_id
        related = []
        if kg.graph.has_node(stock_id):
            for event_src, _, ev_data in kg.graph.in_edges(stock_id, data=True):
                ev_edge = ev_data.get("edge_data")
                if ev_edge and ev_edge.edge_type == KGEdgeType.IMPACTS:
                    event_node = kg.graph.nodes[event_src].get("data")
                    if event_node:
                        related.append({
                            "event_id": event_node.event_id,
                            "event_type": event_node.event_type,
                            "subtype": event_node.subtype,
                            "polarity": ev_edge.polarity,
                            "magnitude": ev_edge.magnitude,
                        })
        return related

    return []
