"""Protocols shared by optional fund-agent sub-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class AgentContext:
    report_date: str
    evidence: Mapping[str, Any]
    prompts: dict[str, str] = field(default_factory=dict)
    tool_names: tuple[str, ...] = field(default_factory=tuple)

    _registry: Any = field(default=None, repr=False)

    @property
    def registry(self):
        if self._registry is None:
            from src.tools.registry import default_registry
            self._registry = default_registry()
            object.__setattr__(self, "_registry", self._registry)
        return self._registry

    def with_registry(self, registry) -> AgentContext:
        object.__setattr__(self, "_registry", registry)
        return self

    def fund_evidence(self, code: str) -> Mapping[str, Any]:
        return (self.evidence.get("funds") or {}).get(str(code), {})


@dataclass(frozen=True)
class AgentOpinion:
    agent: str
    payload: Mapping[str, Any]
    confidence: float | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str
    output: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == "ok"
