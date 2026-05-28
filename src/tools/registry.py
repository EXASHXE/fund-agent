"""Small typed tool registry for future Agent tool binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


ToolCallable = Callable[..., Any]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: ToolCallable
    agents: tuple[str, ...] = field(default_factory=tuple)
    readonly: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        if not tool.name:
            raise ValueError("工具名称不能为空")
        if tool.name in self._tools:
            raise ValueError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def tool(
        self,
        name: str,
        description: str,
        agents: Iterable[str] = (),
        readonly: bool = True,
    ):
        """Decorator for registering a function as a tool."""
        def decorator(func: ToolCallable) -> ToolCallable:
            self.register(ToolDefinition(
                name=name,
                description=description,
                handler=func,
                agents=tuple(agents),
                readonly=readonly,
            ))
            return func

        return decorator

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"未知工具: {name}") from exc

    def list(self, agent: str | None = None) -> list[ToolDefinition]:
        if agent is None:
            return list(self._tools.values())
        return [
            tool for tool in self._tools.values()
            if not tool.agents or agent in tool.agents
        ]

    def invoke(self, name: str, **kwargs) -> Any:
        return self.get(name).handler(**kwargs)


def default_registry() -> ToolRegistry:
    """Return an empty registry for callers to bind project services explicitly."""
    return ToolRegistry()
