"""Host-native MCP adapter contracts.

This module declares the boundary between Research OS tools/skills and a host
that injects MCP capabilities. It intentionally does not import provider SDKs
or perform network IO.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass
class MCPCapability:
    """A host-declared MCP capability."""

    name: str
    input_schema: dict
    output_schema: dict
    priority: int = 100
    fallback: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class MCPHostAdapter:
    """Abstract host MCP boundary."""

    def list_capabilities(self) -> list[MCPCapability]:
        raise NotImplementedError

    def has_capability(self, name: str) -> bool:
        return any(capability.name == name for capability in self.list_capabilities())

    def call(self, name: str, payload: dict) -> dict:
        raise NotImplementedError


class InMemoryMCPHostAdapter(MCPHostAdapter):
    """Test adapter backed by in-memory capability handlers."""

    def __init__(
        self,
        capabilities: list[MCPCapability] | None = None,
        handlers: dict[str, Callable[[dict], dict]] | None = None,
    ) -> None:
        self._capabilities = {
            capability.name: capability
            for capability in capabilities or []
        }
        self._handlers = dict(handlers or {})

    def register(
        self,
        capability: MCPCapability,
        handler: Callable[[dict], dict] | None = None,
    ) -> None:
        self._capabilities[capability.name] = capability
        if handler is not None:
            self._handlers[capability.name] = handler

    def list_capabilities(self) -> list[MCPCapability]:
        return sorted(
            self._capabilities.values(),
            key=lambda capability: (capability.priority, capability.name),
        )

    def call(self, name: str, payload: dict) -> dict:
        if name not in self._capabilities:
            return {
                "ok": False,
                "error": {
                    "type": "missing_capability",
                    "message": f"MCP capability '{name}' is not available",
                    "capability": name,
                },
            }

        handler = self._handlers.get(name)
        if handler is None:
            return {
                "ok": False,
                "error": {
                    "type": "missing_handler",
                    "message": f"MCP capability '{name}' has no handler",
                    "capability": name,
                },
            }

        try:
            result = handler(dict(payload))
        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "capability": name,
                },
            }

        if not isinstance(result, dict):
            return {
                "ok": False,
                "error": {
                    "type": "invalid_response",
                    "message": "MCP capability handler must return a dict",
                    "capability": name,
                },
            }
        return {"ok": True, "data": result}
