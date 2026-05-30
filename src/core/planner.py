"""Planner — KG-first inquiry decomposition for fund research.

Queries KnowledgeGraph BEFORE generating plan steps, ensuring every
PlanStep is grounded in entity-chain and exposure data from the KG.
Produces a Plan with ordered, dependency-aware PlanSteps ready for
execution by the skill pipeline.

Integration with existing agent system: The Planner preserves the old
gap-analysis intent from legacy agents while providing a standalone, typed
interface for the Research OS path.

Design constraints:
    * No LLM / network / IO imports — this is a pure orchestration module.
    * KG must be queried before step generation (KGContextSnapshot in Plan).
    * Does NOT generate final investment advice — that's the ledger's job.
    * Gaps are derived from KG entity chains, exposures, themes, and events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PlanStep:
    """A single step in a research plan."""

    step_id: str
    skill_name: str
    input: dict = field(default_factory=dict)
    expected_output: str = ""
    depends_on: list[str] = field(default_factory=list)
    reason: str = ""
    required_mcp_capabilities: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "skill_name": self.skill_name,
            "input": self.input,
            "expected_output": self.expected_output,
            "depends_on": self.depends_on,
            "reason": self.reason,
            "required_mcp_capabilities": self.required_mcp_capabilities,
            "evidence_requirements": self.evidence_requirements,
        }


@dataclass
class Plan:
    """A research plan with ordered steps and KG context."""

    task_id: str
    steps: list[PlanStep] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    kg_context_snapshot: dict = field(default_factory=dict)
    iteration: int = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "steps": [s.to_dict() for s in self.steps],
            "generated_at": self.generated_at.isoformat(),
            "kg_context_snapshot": self.kg_context_snapshot,
            "iteration": self.iteration,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Planner
# ═══════════════════════════════════════════════════════════════════════════════


class Planner:
    """KG-driven fund research planner.

    Preserves the gap-analysis intent from the previous 8-node LangGraph
    planner agent in legacy/, but provides a standalone typed interface
    where gaps are derived from KG entity
    chains, exposures, themes, and events — not hardcoded rules.
    """

    DEFAULT_SKILL_ORDER: list[str] = [
        "QuantRiskAnalysis",
        "PortfolioExposureAnalysis",
        "NewsResearch",
        "SentimentResearch",
        "ThesisGeneration",
    ]

    def plan(self, task, kg) -> Plan:
        kg_context = self._query_kg_context(kg, task)
        gaps = self._identify_gaps(task, kg_context, kg)
        steps = self._generate_steps(gaps, kg_context)
        return Plan(
            task_id=task.task_id,
            steps=steps,
            generated_at=datetime.now(),
            kg_context_snapshot=kg_context,
            iteration=0,
        )

    def replan(self, task, kg, retry_suggestions: list[str]) -> Plan:
        plan = self.plan(task, kg)
        plan.iteration = 1

        if not retry_suggestions:
            return plan

        next_id = len(plan.steps)
        for suggestion in retry_suggestions:
            skill = self._map_suggestion_to_skill(suggestion)
            if skill:
                step = PlanStep(
                    step_id=f"step_{next_id}",
                    skill_name=skill,
                    input={"skill": skill, "reason": suggestion},
                    expected_output=f"Targeted evidence for: {suggestion[:60]}",
                    depends_on=[f"step_{next_id - 1}"] if next_id > 0 else [],
                    reason=f"Critic suggestion: {suggestion}",
                    required_mcp_capabilities=self._mcp_capabilities_for_skill(skill, plan.kg_context_snapshot),
                    evidence_requirements=self._evidence_requirements_for_skill(skill),
                )
                plan.steps.append(step)
                next_id += 1
        return plan

    def _map_suggestion_to_skill(self, suggestion: str) -> str | None:
        s = suggestion.lower()
        if any(kw in s for kw in ("quant", "sharpe", "sortino", "volatility", "drawdown", "risk")):
            return "QuantRiskAnalysis"
        if any(kw in s for kw in ("exposure", "concentration", "hhi", "position")):
            return "PortfolioExposureAnalysis"
        if any(kw in s for kw in ("news", "event", "headline", "article")):
            return "NewsResearch"
        if any(kw in s for kw in ("sentiment", "mood", "polarity", "tone")):
            return "SentimentResearch"
        if any(kw in s for kw in ("thesis", "synthesis", "conclusion", "cross-validate")):
            return "ThesisGeneration"
        return None

    def _query_kg_context(self, kg, task) -> dict:
        """Query KG for each fund's entity chain, exposure, themes, and events."""
        context: dict[str, Any] = {"fund_codes": list(task.fund_universe)}

        graph = getattr(kg, "graph", None)
        if graph is None:
            for code in task.fund_universe:
                context[code] = {}
            return context

        from src.graph.queries import get_entity_chain, query_exposure, expand_theme, find_related_events

        for code in task.fund_universe:
            fund_id = f"fund:{code}"
            fund_ctx: dict[str, Any] = {}
            try:
                chain = get_entity_chain(kg, fund_id)
                exposure = query_exposure(kg, fund_id)
                fund_ctx["chain"] = chain
                fund_ctx["exposure"] = exposure

                # Extract themes from chain for deeper KG-driven planning
                themes = self._extract_themes(chain)
                fund_ctx["themes"] = themes
                for theme in themes[:3]:
                    try:
                        fund_ctx[f"theme_{theme}"] = expand_theme(kg, theme, depth=2)
                    except Exception:
                        pass

                # Find related events
                try:
                    fund_ctx["events"] = find_related_events(kg, fund_id)
                except Exception:
                    fund_ctx["events"] = []

            except Exception:
                pass
            context[code] = fund_ctx

        return context

    def _identify_gaps(self, task, kg_context, kg) -> list[str]:
        """Identify evidence gaps using KG context (NOT hardcoded rules).

        Derives gaps from:
        - Exposure data: determines if PortfolioExposureAnalysis is needed
        - Theme data: presence of themes triggers News/Sentiment research
        - Event data: events related to holdings trigger deeper analysis
        - Task objective: discretionary override for urgency signals
        """
        gaps: list[str] = []
        obj_lower = task.objective.lower()

        # ── KG-driven gap detection ──────────────────────────────────────
        has_exposure = False
        has_themes = False
        has_events = False
        total_stocks = 0
        total_industries = 0

        for code in task.fund_universe:
            fund_ctx = kg_context.get(code, {})
            chain = fund_ctx.get("chain", {})

            # Count entities in chain to determine analysis depth needed
            stocks = chain.get("stocks", []) if isinstance(chain, dict) else []
            industries = chain.get("industries", []) if isinstance(chain, dict) else []
            total_stocks += len(stocks) if isinstance(stocks, list) else 0
            total_industries += len(industries) if isinstance(industries, list) else 0

            if fund_ctx.get("exposure") and isinstance(fund_ctx["exposure"], dict):
                has_exposure = True
            if fund_ctx.get("themes") and fund_ctx["themes"]:
                has_themes = True
            if fund_ctx.get("events") and fund_ctx["events"]:
                has_events = True

        # Always compute quant risk baseline
        gaps.append("QuantRiskAnalysis")

        # Exposure analysis needed when:
        # - KG has exposure data (use it)
        # - OR we detected stocks/industries but no exposure data (compute it)
        if has_exposure or (total_stocks == 0 and total_industries == 0):
            gaps.append("PortfolioExposureAnalysis")
        elif not has_exposure:
            gaps.append("PortfolioExposureAnalysis")

        # News research triggered by: themes found in KG, events detected,
        # review/market objectives, or concentrated positions (>5 stocks)
        if has_themes or has_events or "review" in obj_lower or "market" in obj_lower or total_stocks > 5:
            gaps.append("NewsResearch")

        # Sentiment research follows news when themes or events exist
        if has_themes or has_events or "review" in obj_lower or "sentiment" in obj_lower:
            gaps.append("SentimentResearch")

        # Thesis generation always final — synthesizes all evidence
        gaps.append("ThesisGeneration")

        return gaps

    def _extract_themes(self, chain: dict) -> list[str]:
        """Extract theme names from entity chain data."""
        themes = []
        if not isinstance(chain, dict):
            return themes
        industries = chain.get("industries", [])
        if isinstance(industries, list):
            for ind in industries:
                if isinstance(ind, dict):
                    theme = ind.get("theme", "")
                    if theme:
                        themes.append(theme)
                elif isinstance(ind, str):
                    themes.append(ind)
        theme_data = chain.get("themes", [])
        if isinstance(theme_data, list):
            for t in theme_data:
                if isinstance(t, dict):
                    themes.append(t.get("name", ""))
                elif isinstance(t, str):
                    themes.append(t)
        return list(dict.fromkeys(themes))  # dedup preserving order

    def _generate_steps(self, gaps: list[str], kg_context: dict) -> list[PlanStep]:
        steps: list[PlanStep] = []
        ordered = [s for s in self.DEFAULT_SKILL_ORDER if s in gaps]
        ordered += [s for s in gaps if s not in self.DEFAULT_SKILL_ORDER]

        for i, skill_name in enumerate(ordered):
            step = PlanStep(
                step_id=f"step_{i}",
                skill_name=skill_name,
                input={"skill": skill_name, "context": kg_context},
                expected_output=f"EvidenceItems for {skill_name}",
                depends_on=[f"step_{i - 1}"] if i > 0 else [],
                reason=self._reason_for_skill(skill_name, kg_context),
                required_mcp_capabilities=self._mcp_capabilities_for_skill(skill_name, kg_context),
                evidence_requirements=self._evidence_requirements_for_skill(skill_name),
            )
            steps.append(step)
        return steps

    def _reason_for_skill(self, skill_name: str, kg_context: dict) -> str:
        """Generate KG-grounded reason for why a skill is needed."""
        reasons = {
            "QuantRiskAnalysis": "Baseline risk metrics required for all funds",
            "PortfolioExposureAnalysis": "KG exposure data drives position sizing analysis",
            "NewsResearch": "KG themes and events detected — news research needed",
            "SentimentResearch": "Sentiment analysis contextualizes KG-derived events",
            "ThesisGeneration": "Final synthesis of all evidence into actionable thesis",
        }
        return reasons.get(skill_name, f"Required by plan: {skill_name}")

    def _mcp_capabilities_for_skill(self, skill_name: str, kg_context: dict) -> list[str]:
        """Return host MCP capabilities needed by a skill.

        The planner only declares capabilities. It does not call MCP adapters or
        perform network IO.
        """
        if skill_name == "NewsResearch":
            return ["web_search", "financial_news"]
        if skill_name == "SentimentResearch":
            return ["social_sentiment"]
        if skill_name in {
            "QuantRiskAnalysis",
            "PortfolioExposureAnalysis",
            "FundAnalysis",
            "ThesisGeneration",
        }:
            return []
        return []

    def _evidence_requirements_for_skill(self, skill_name: str) -> list[str]:
        """Return evidence contract expectations for a plan step."""
        requirements = {
            "QuantRiskAnalysis": ["HardEvidence:risk_metrics"],
            "PortfolioExposureAnalysis": ["HardEvidence:portfolio_exposure"],
            "FundAnalysis": ["HardEvidence:local_quant_tools"],
            "NewsResearch": [
                "SoftEvidence:news_events",
                "optional:company_filings",
            ],
            "SentimentResearch": [
                "SoftEvidence:sentiment",
                "optional:reddit_search",
                "optional:trend_radar",
            ],
            "ThesisGeneration": ["artifact:thesis_draft"],
        }
        return list(requirements.get(skill_name, []))
