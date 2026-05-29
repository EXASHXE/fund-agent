"""Events module: taxonomy, extraction, and enrichment for news events."""
from legacy.events.taxonomy import (
    EventCategory, EventType, EVENT_HIERARCHY, EVENT_KEYWORDS,
    ClassifiedEvent, get_event_type, classify_event,
)
from legacy.events.extractor import extract_events_from_text

__all__ = [
    "EventCategory", "EventType", "EVENT_HIERARCHY", "EVENT_KEYWORDS",
    "ClassifiedEvent", "get_event_type", "classify_event",
    "extract_events_from_text",
]