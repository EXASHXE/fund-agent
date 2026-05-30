"""SkillRegistry runtime contract tests."""

from __future__ import annotations

import ast
from pathlib import Path

from src.core.skill_registry import SkillRegistry
from src.schemas.skill import SkillInput, SkillOutput
from src.tools.adapters.mcp import InMemoryMCPHostAdapter


def test_skill_registry_runs_registered_skill():
    registry = SkillRegistry()
    registry.register_skill(
        "EchoSkill",
        lambda skill_input: SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts={"payload": skill_input.payload},
        ),
    )

    output = registry.run_skill(_input("EchoSkill", payload={"x": 1}))

    assert output.status == "OK"
    assert output.artifacts["payload"] == {"x": 1}


def test_missing_skill_returns_failed_skill_output():
    output = SkillRegistry().run_skill(_input("MissingSkill"))

    assert output.status == "FAILED"
    assert output.errors
    assert output.errors[0]["type"] == "KeyError"


def test_skill_exception_returns_structured_error():
    registry = SkillRegistry()

    def _raise(_):
        raise RuntimeError("boom")

    registry.register_skill("ExplodingSkill", _raise)
    output = registry.run_skill(_input("ExplodingSkill"))

    assert output.status == "FAILED"
    assert output.errors[0]["type"] == "RuntimeError"
    assert "boom" in output.errors[0]["message"]


def test_skill_registry_passes_mcp_adapter_to_skill():
    adapter = InMemoryMCPHostAdapter()
    registry = SkillRegistry(mcp_adapter=adapter)
    handler = _AdapterAwareSkill()
    registry.register_skill("AdapterAware", handler)

    output = registry.run_skill(_input("AdapterAware"))

    assert output.status == "OK"
    assert handler.seen_adapter is adapter


def test_missing_required_mcp_capability_is_reported():
    registry = SkillRegistry(mcp_adapter=InMemoryMCPHostAdapter())
    registry.register_skill("NeedsMCP", lambda _: SkillOutput())

    output = registry.run_skill(
        _input("NeedsMCP", required_mcp_capabilities=["web_search"])
    )

    assert output.status == "FAILED"
    assert output.errors[0]["type"] == "MissingMCPCapability"
    assert output.errors[0]["missing_capabilities"] == ["web_search"]


def test_skill_registry_does_not_import_provider_sdks():
    imports = _imports_from(Path("src/core/skill_registry.py"))
    forbidden = {"tavily", "finnhub", "exa", "firecrawl", "reddit"}

    assert not (imports & forbidden)


class _AdapterAwareSkill:
    mcp_adapter = None
    seen_adapter = None

    def run(self, skill_input: SkillInput) -> SkillOutput:
        self.seen_adapter = self.mcp_adapter
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
        )


def _input(
    skill_name: str,
    payload: dict | None = None,
    required_mcp_capabilities: list[str] | None = None,
) -> SkillInput:
    return SkillInput(
        task_id="task-1",
        step_id="step-1",
        skill_name=skill_name,
        payload=payload or {},
        required_mcp_capabilities=required_mcp_capabilities or [],
    )


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports
