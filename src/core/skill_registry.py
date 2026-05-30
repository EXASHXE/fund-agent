"""Optional in-process skill registry.

External agent hosts can instantiate skills directly from the skill pack
manifest. This registry is a convenience/reference helper, not a required host
integration layer.
"""

from dataclasses import dataclass, field
from typing import Any

from src.schemas.skill import SkillInput, SkillOutput


@dataclass
class SkillDefinition:
    """Definition of a registered skill."""

    name: str
    handler: Any
    purpose: str = ""
    required_mcp_capabilities: list[str] = field(default_factory=list)
    priority: int = 3
    forbidden_behavior: list[str] = field(default_factory=list)


class SkillRegistry:
    """Registry for skill registration and execution."""

    def __init__(self, tool_registry: Any = None, mcp_adapter: Any = None):
        self._skills: dict[str, SkillDefinition] = {}
        self.tool_registry = tool_registry
        self.mcp_adapter = mcp_adapter

    def register(self, skill: SkillDefinition) -> None:
        """Register a skill. Raises ValueError if name already exists."""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        """Get a registered skill. Raises KeyError if not found."""
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not found in registry")
        return self._skills[name]

    def register_skill(self, name: str, handler: Any) -> None:
        """Register a runtime skill handler by name."""
        self.register(SkillDefinition(name=name, handler=handler))

    def run_skill(self, skill_input: SkillInput) -> SkillOutput:
        """Run a registered skill with the structured runtime contract.

        Missing skills, missing MCP capabilities, and handler exceptions are
        returned as structured ``SkillOutput`` failures.
        """
        try:
            skill = self.get(skill_input.skill_name)
        except KeyError as exc:
            return self._failed_output(
                skill_input,
                error_type="KeyError",
                message=str(exc),
            )

        required = list(
            dict.fromkeys(
                list(skill_input.required_mcp_capabilities)
                + list(skill.required_mcp_capabilities)
            )
        )
        missing = [
            capability
            for capability in required
            if self.mcp_adapter is None
            or not self.mcp_adapter.has_capability(capability)
        ]
        if missing:
            return self._failed_output(
                skill_input,
                error_type="MissingMCPCapability",
                message=(
                    "Missing required MCP capability: "
                    + ", ".join(missing)
                ),
                details={"missing_capabilities": missing},
            )

        try:
            result = self._invoke_handler(skill.handler, skill_input)
        except Exception as exc:
            return self._failed_output(
                skill_input,
                error_type=type(exc).__name__,
                message=str(exc),
            )

        output = self._coerce_output(result, skill_input)
        output.step_id = output.step_id or skill_input.step_id
        output.skill_name = output.skill_name or skill_input.skill_name
        return output

    def run(self, name: str, input_data: dict = None) -> SkillOutput:
        """Run a registered skill with legacy dict input data."""
        skill = self.get(name)
        skill_input = SkillInput(
            task_id="",
            step_id="",
            skill_name=name,
            payload=input_data or {},
            required_mcp_capabilities=list(skill.required_mcp_capabilities),
        )
        try:
            result = self._invoke_handler(
                skill.handler,
                skill_input,
                legacy_payload=True,
            )
            return self._coerce_output(result, skill_input)
        except Exception as e:
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=name,
                artifacts={
                    "skill_error": str(e),
                    "error_type": type(e).__name__,
                },
                warnings=[str(e)],
                errors=[
                    {
                        "type": type(e).__name__,
                        "message": str(e),
                        "skill_name": name,
                    }
                ],
                status="FAILED",
            )

    def list_skills(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def unregister(self, name: str) -> None:
        """Unregister a skill."""
        self._skills.pop(name, None)

    def _invoke_handler(
        self,
        handler: Any,
        skill_input: SkillInput,
        legacy_payload: bool = False,
    ) -> Any:
        if hasattr(handler, "mcp_adapter"):
            handler.mcp_adapter = self.mcp_adapter
        if hasattr(handler, "tool_registry"):
            handler.tool_registry = self.tool_registry
        if hasattr(handler, "run") and callable(handler.run):
            return handler.run(skill_input)
        if callable(handler):
            return handler(skill_input.payload if legacy_payload else skill_input)
        raise TypeError("Skill handler must be callable or expose run(input)")

    def _coerce_output(self, result: Any, skill_input: SkillInput) -> SkillOutput:
        if isinstance(result, SkillOutput):
            return result
        if isinstance(result, dict):
            return SkillOutput(
                step_id=result.get("step_id", skill_input.step_id),
                skill_name=result.get("skill_name", skill_input.skill_name),
                evidence_items=result.get("evidence_items", []),
                artifacts=result.get("artifacts", {}),
                warnings=result.get("warnings", []),
                errors=result.get("errors", []),
                used_mcp_capabilities=result.get("used_mcp_capabilities", []),
                status=result.get("status", "OK"),
            )
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
        )

    def _failed_output(
        self,
        skill_input: SkillInput,
        *,
        error_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> SkillOutput:
        error = {
            "type": error_type,
            "message": message,
            "step_id": skill_input.step_id,
            "skill_name": skill_input.skill_name,
        }
        if details:
            error.update(details)
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts={"skill_error": message, "error_type": error_type},
            warnings=[message],
            errors=[error],
            status="FAILED",
        )


# Default registry singleton
default_registry = SkillRegistry()


def bootstrap_default_registry(registry: SkillRegistry | None = None) -> SkillRegistry:
    """Bootstrap the default registry with production skill handlers.

    Registers the 4 core skills (QuantRiskAnalysis, NewsResearch,
    SentimentResearch, ThesisGeneration) using their production
    Python implementations.

    Args:
        registry: Optional existing registry. Creates one if None.

    Returns:
        The populated SkillRegistry.
    """
    if registry is None:
        registry = SkillRegistry()

    # ── QuantRiskAnalysis ────────────────────────────────────────────────
    try:
        from src.skills_runtime.fund_analysis import FundAnalysisSkill
        skill = FundAnalysisSkill()
        registry.register(SkillDefinition(
            name="QuantRiskAnalysis",
            handler=skill,
            purpose="Quantitative risk analysis and score computation",
            required_mcp_capabilities=[],
            priority=1,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    # ── PortfolioExposureAnalysis ─────────────────────────────────────────
    try:
        registry.register(SkillDefinition(
            name="PortfolioExposureAnalysis",
            handler=lambda inp: SkillOutput(
                evidence_items=[],
                artifacts={"note": "PortfolioExposure delegates to KG queries"},
            ),
            purpose="Portfolio exposure analysis via KnowledgeGraph",
            required_mcp_capabilities=[],
            priority=2,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except Exception:
        pass

    # ── NewsResearch ─────────────────────────────────────────────────────
    try:
        from src.skills_runtime.news_research import NewsResearchSkill
        skill = NewsResearchSkill()
        registry.register(SkillDefinition(
            name="NewsResearch",
            handler=skill,
            purpose="Holdings-driven news research and event mining",
            required_mcp_capabilities=["web_search", "financial_news"],
            priority=2,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    # ── SentimentResearch ────────────────────────────────────────────────
    try:
        from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
        skill = SentimentAnalysisSkill()
        registry.register(SkillDefinition(
            name="SentimentResearch",
            handler=skill,
            purpose="Financial market sentiment analysis",
            required_mcp_capabilities=["social_sentiment"],
            priority=3,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    # ── ThesisGeneration ─────────────────────────────────────────────────
    try:
        from src.skills_runtime.thesis_generation import ThesisGenerationSkill
        skill = ThesisGenerationSkill()
        registry.register(SkillDefinition(
            name="ThesisGeneration",
            handler=skill,
            purpose="Investment thesis generation and evidence validation",
            required_mcp_capabilities=[],
            priority=4,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    return registry
