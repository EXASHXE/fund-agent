"""Thin cache wrapper for KnowledgeGraph pickle persistence."""
import os
import pickle
from datetime import datetime, timedelta


def save_kg_cache(kg_graph, path: str) -> None:
    """Persist knowledge graph to a pickle file.

    Args:
        kg_graph: A NetworkX DiGraph to cache.
        path: Filesystem path for the cache file.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(kg_graph, f)


def load_kg_cache(path: str, max_age_hours: int = 24):
    """Load a cached knowledge graph, respecting max age.

    Args:
        path: Filesystem path to the cached pickle file.
        max_age_hours: Maximum age in hours before cache is considered stale.

    Returns:
        The loaded NetworkX DiGraph, or ``None`` if not found or expired.
    """
    if not os.path.exists(path):
        return None

    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    if age > timedelta(hours=max_age_hours):
        return None

    with open(path, "rb") as f:
        return pickle.load(f)


def kg_cache_key(fund_codes: list[str]) -> str:
    """Generate a deterministic cache filename from sorted fund codes.

    Args:
        fund_codes: List of fund code strings (e.g. ``["110011", "006123"]``).

    Returns:
        A stable filename like ``kg_006123_110011.pkl``.
    """
    return "kg_" + "_".join(sorted(fund_codes)) + ".pkl"
