"""Event extraction from news text. LLM-based extraction reserved for Phase 2."""
from __future__ import annotations

from legacy.events.taxonomy import ClassifiedEvent, classify_event


def extract_events_from_text(
    text: str,
    use_llm: bool = False,
    llm_client: object | None = None,  # accepted by pipeline, reserved for Phase 2+
) -> list[ClassifiedEvent]:
    """Extract structured events from news text.

    Phase 1: Rule-based classification only.
    Phase 2: Will add LLM-based extraction.

    Args:
        text: News headline or content to extract events from.
        use_llm: Whether to use LLM for extraction (reserved for Phase 2).

    Returns:
        List of ClassifiedEvent objects.
    """
    # Phase 1: Rule-based only
    event = classify_event(text)
    if event.event_type.value == "other" and not text.strip():
        return []
    return [event]