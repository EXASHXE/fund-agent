"""Deterministic workflow trace builder.

Records workflow events in sequence order. No wall-clock timestamps,
no chain-of-thought, no secrets, no credentials.

Each event has a monotonically increasing sequence number starting at 1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowTrace:
    scenario_id: str | None = None
    _events: list[dict] = field(default_factory=list)
    _seq: int = field(default=0, init=False)

    def add_event(
        self,
        event_type: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self._seq += 1
        event: dict[str, Any] = {
            "sequence": self._seq,
            "type": event_type,
            "message": message,
        }
        if details:
            redacted = _redact_secrets(details)
            event["details"] = redacted
        self._events.append(event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "event_count": len(self._events),
            "events": list(self._events),
        }

    def to_jsonl(self) -> str:
        lines: list[str] = []
        for event in self._events:
            lines.append(json.dumps(event, ensure_ascii=False, sort_keys=True))
        return "\n".join(lines)

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    def last_event_type(self) -> str | None:
        if self._events:
            return self._events[-1].get("type")
        return None


_SECRET_KEYS = frozenset({
    "api_key", "token", "cookie", "password", "secret",
    "authorization", "credentials", "xueqiu_cookie", "eastmoney_cookie",
})


def _redact_secrets(details: dict) -> dict:
    redacted: dict[str, Any] = {}
    for key, value in details.items():
        lk = key.lower()
        if any(s in lk for s in _SECRET_KEYS):
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = _redact_secrets(value)
        else:
            redacted[key] = value
    return redacted
