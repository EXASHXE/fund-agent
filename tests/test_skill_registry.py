"""Tests for Skill Registry module."""

import pytest

from src.core.skill_registry import (
    SkillRegistry,
    SkillDefinition,
    SkillOutput,
    default_registry,
)


def _mock_handler(input_data: dict) -> dict:
    return {
        "evidence_items": ["item1", "item2"],
        "artifacts": {"score": 0.85},
        "warnings": [],
    }


def _mock_handler_raises(input_data: dict) -> None:
    raise RuntimeError("handler failure")


def _mock_handler_skilloutput(input_data: dict) -> SkillOutput:
    return SkillOutput(
        evidence_items=["direct_item"],
        artifacts={"direct": True},
        warnings=["sample warning"],
    )


class TestSkillOutput:
    """Tests for SkillOutput dataclass."""

    def test_default_values(self):
        output = SkillOutput()
        assert output.evidence_items == []
        assert output.artifacts == {}
        assert output.warnings == []

    def test_to_dict_with_plain_items(self):
        output = SkillOutput(
            evidence_items=["a", "b"],
            artifacts={"k": "v"},
            warnings=["w1"],
        )
        d = output.to_dict()
        assert d["evidence_items"] == ["a", "b"]
        assert d["artifacts"] == {"k": "v"}
        assert d["warnings"] == ["w1"]

    def test_to_dict_with_to_dict_items(self):
        class WithToDict:
            def to_dict(self):
                return {"val": 42}

        item = WithToDict()
        output = SkillOutput(evidence_items=[item])
        d = output.to_dict()
        assert d["evidence_items"] == [{"val": 42}]


class TestSkillRegistry:
    """Tests for SkillRegistry class."""

    def test_register_skill(self):
        registry = SkillRegistry()
        skill = SkillDefinition(name="test", handler=_mock_handler)
        registry.register(skill)
        assert "test" in registry.list_skills()

    def test_register_duplicate_raises(self):
        registry = SkillRegistry()
        skill = SkillDefinition(name="test", handler=_mock_handler)
        registry.register(skill)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(skill)

    def test_get_missing_raises_keyerror(self):
        registry = SkillRegistry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.get("nonexistent")

    def test_get_registered_skill(self):
        registry = SkillRegistry()
        skill = SkillDefinition(
            name="analyze",
            handler=_mock_handler,
            purpose="analysis",
            required_mcp_capabilities=["MCP1"],
            priority=1,
            forbidden_behavior=["no_network"],
        )
        registry.register(skill)
        retrieved = registry.get("analyze")
        assert retrieved.name == "analyze"
        assert retrieved.purpose == "analysis"
        assert retrieved.required_mcp_capabilities == ["MCP1"]
        assert retrieved.priority == 1
        assert retrieved.forbidden_behavior == ["no_network"]

    def test_run_skill_returns_output_from_dict(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(name="test", handler=_mock_handler))
        result = registry.run("test", {"key": "value"})
        assert isinstance(result, SkillOutput)
        assert result.evidence_items == ["item1", "item2"]
        assert result.artifacts == {"score": 0.85}
        assert result.warnings == []

    def test_run_skill_returns_skilloutput_directly(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(name="test", handler=_mock_handler_skilloutput))
        result = registry.run("test")
        assert isinstance(result, SkillOutput)
        assert result.evidence_items == ["direct_item"]
        assert result.artifacts == {"direct": True}
        assert result.warnings == ["sample warning"]

    def test_run_missing_skill_raises(self):
        registry = SkillRegistry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.run("nonexistent")

    def test_run_skill_catches_handler_exception(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(name="failing", handler=_mock_handler_raises))
        result = registry.run("failing")
        assert isinstance(result, SkillOutput)
        assert "handler failure" in result.warnings[0]

    def test_list_skills(self):
        registry = SkillRegistry()
        assert registry.list_skills() == []
        registry.register(SkillDefinition(name="a", handler=_mock_handler))
        registry.register(SkillDefinition(name="b", handler=_mock_handler))
        assert sorted(registry.list_skills()) == ["a", "b"]

    def test_unregister_skill(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(name="temp", handler=_mock_handler))
        assert "temp" in registry.list_skills()
        registry.unregister("temp")
        assert "temp" not in registry.list_skills()

    def test_unregister_nonexistent_does_not_raise(self):
        registry = SkillRegistry()
        registry.unregister("no_such_skill")  # should not raise
        assert registry.list_skills() == []


class TestDefaultRegistry:
    """Tests for the default_registry singleton."""

    def test_default_registry_is_instance(self):
        assert isinstance(default_registry, SkillRegistry)

    def test_default_registry_starts_empty(self):
        # Clear any leftovers
        for name in list(default_registry._skills.keys()):
            default_registry.unregister(name)
        assert default_registry.list_skills() == []

    def test_default_registry_register_and_run(self):
        handler = _mock_handler_skilloutput
        default_registry.register(
            SkillDefinition(name="default_test", handler=handler, priority=2)
        )
        result = default_registry.run("default_test")
        assert isinstance(result, SkillOutput)
        assert result.artifacts == {"direct": True}
        default_registry.unregister("default_test")
