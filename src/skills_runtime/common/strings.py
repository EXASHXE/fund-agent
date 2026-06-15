"""Shared string deduplication utility."""

from __future__ import annotations

from typing import Any


def unique_strings(
    *groups: Any,
    skip_empty: bool = True,
) -> list[str]:
    """Return deduplicated strings preserving first-occurrence order.

    Args:
        *groups: One or more groups of values. Each group can be:
            - A list/iterable of values (each converted via str())
            - A single string value
            - None (skipped)
        skip_empty: If True, skip empty strings after str() conversion.
            Defaults to True.

    Returns:
        List of unique, non-empty strings in first-occurrence order.
    """
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if group is None:
            continue
        if isinstance(group, str):
            values = [group]
        else:
            values = list(group or [])
        for value in values:
            text = str(value)
            if skip_empty and not text:
                continue
            if text not in seen:
                result.append(text)
                seen.add(text)
    return result
