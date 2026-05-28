"""Minimal multi-agent orchestrator boundary.

This module does not call an LLM. It coordinates named runner callables so the
project can evolve from external Agent decisions to tool-bound sub-agents
without changing the report/decision contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from src.agents.protocols import AgentContext, AgentOpinion, StageResult


AgentRunner = Callable[[AgentContext], AgentOpinion]


@dataclass(frozen=True)
class OrchestrationResult:
    opinions: tuple[AgentOpinion, ...] = field(default_factory=tuple)
    stages: tuple[StageResult, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(stage.ok for stage in self.stages)


class AgentOrchestrator:
    def __init__(self, runners: dict[str, AgentRunner] | None = None) -> None:
        self._runners: dict[str, AgentRunner] = dict(runners or {})

    def register(self, name: str, runner: AgentRunner) -> None:
        if not name:
            raise ValueError("Agent 名称不能为空")
        if name in self._runners:
            raise ValueError(f"Agent 已注册: {name}")
        self._runners[name] = runner

    def run(self, context: AgentContext, plan: Iterable[str]) -> OrchestrationResult:
        opinions: list[AgentOpinion] = []
        stages: list[StageResult] = []

        for name in plan:
            runner = self._runners.get(name)
            if runner is None:
                stages.append(StageResult(name=name, status="error", errors=(f"未注册 Agent: {name}",)))
                continue
            try:
                opinion = runner(context)
            except Exception as exc:  # pragma: no cover - exact exception type belongs to runner
                stages.append(StageResult(name=name, status="error", errors=(str(exc),)))
                continue
            opinions.append(opinion)
            stages.append(StageResult(name=name, status="ok", output=dict(opinion.payload)))

        return OrchestrationResult(opinions=tuple(opinions), stages=tuple(stages))
