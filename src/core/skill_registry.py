"""Skill Registry — manages skill registration and execution."""

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class SkillOutput:
    """Output from a skill execution."""

    evidence_items: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_items": [
                e.to_dict() if hasattr(e, "to_dict") else e
                for e in self.evidence_items
            ],
            "artifacts": self.artifacts,
            "warnings": self.warnings,
        }


@dataclass
class SkillDefinition:
    """Definition of a registered skill."""

    name: str
    handler: Callable
    purpose: str = ""
    required_mcp_capabilities: list[str] = field(default_factory=list)
    priority: int = 3
    forbidden_behavior: list[str] = field(default_factory=list)


class SkillRegistry:
    """Registry for skill registration and execution."""

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}

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

    def run(self, name: str, input_data: dict = None) -> SkillOutput:
        """Run a registered skill with input data."""
        skill = self.get(name)
        try:
            result = skill.handler(input_data or {})
            if isinstance(result, SkillOutput):
                return result
            # Wrap raw result
            if isinstance(result, dict):
                return SkillOutput(
                    evidence_items=result.get("evidence_items", []),
                    artifacts=result.get("artifacts", {}),
                    warnings=result.get("warnings", []),
                )
            return SkillOutput()
        except Exception as e:
            return SkillOutput(
                artifacts={
                    "skill_error": str(e),
                    "error_type": type(e).__name__,
                },
                warnings=[str(e)],
            )

    def list_skills(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def unregister(self, name: str) -> None:
        """Unregister a skill."""
        self._skills.pop(name, None)


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
        from skills.fund_analysis.skill import FundAnalysisSkill
        skill = FundAnalysisSkill()
        registry.register(SkillDefinition(
            name="QuantRiskAnalysis",
            handler=lambda inp: skill.run(inp) if hasattr(skill, 'run') else SkillOutput(
                evidence_items=[],
                artifacts={"note": "FundAnalysisSkill registered as QuantRiskAnalysis"},
            ),
            purpose="Quantitative risk analysis and score computation",
            required_mcp_capabilities=["TrendRadar", "Tavily"],
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
        from skills.news_research.skill import NewsResearchSkill
        skill = NewsResearchSkill()
        registry.register(SkillDefinition(
            name="NewsResearch",
            handler=lambda inp: skill.run(inp) if hasattr(skill, 'run') else SkillOutput(
                evidence_items=[],
                artifacts={"note": "NewsResearchSkill registered"},
            ),
            purpose="Holdings-driven news research and event mining",
            required_mcp_capabilities=["Finnhub", "Tavily", "Exa", "Firecrawl"],
            priority=2,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    # ── SentimentResearch ────────────────────────────────────────────────
    try:
        from skills.sentiment_analysis.skill import SentimentAnalysisSkill
        skill = SentimentAnalysisSkill()
        registry.register(SkillDefinition(
            name="SentimentResearch",
            handler=lambda inp: skill.run(inp) if hasattr(skill, 'run') else SkillOutput(
                evidence_items=[],
                artifacts={"note": "SentimentAnalysisSkill registered"},
            ),
            purpose="Financial market sentiment analysis",
            required_mcp_capabilities=["Reddit", "TrendRadar"],
            priority=3,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    # ── ThesisGeneration ─────────────────────────────────────────────────
    try:
        from skills.thesis_generation.skill import ThesisGenerationSkill
        skill = ThesisGenerationSkill()
        registry.register(SkillDefinition(
            name="ThesisGeneration",
            handler=lambda inp: skill.run(inp) if hasattr(skill, 'run') else SkillOutput(
                evidence_items=[],
                artifacts={"note": "ThesisGenerationSkill registered"},
            ),
            purpose="Investment thesis generation and evidence validation",
            required_mcp_capabilities=["TrendRadar", "Tavily", "Exa", "Firecrawl", "Finnhub", "Reddit"],
            priority=4,
            forbidden_behavior=["Do NOT generate final BUY/SELL decisions"],
        ))
    except ImportError:
        pass

    return registry
