"""Supervisor agent: routes tasks to specialized agents based on state."""
from __future__ import annotations

from src.agents.state import FundResearchState

# Agent execution order: news first, then quant/risk parallel, then research, then strategy
AGENT_ORDER = ["news", "quant", "risk", "research", "strategy"]

# Which agents can run in parallel
PARALLEL_GROUPS = [
    {"quant", "risk"},
]


def get_supervisor_routing(state: FundResearchState) -> dict:
    """Determine which agent should run next based on current state.

    The supervisor follows a fixed order optimized for data dependencies:
    1. NEWS: Collect and process news (needed by all other agents)
    2. QUANT + RISK: Compute quantitative and risk scores (parallel)
    3. RESEARCH: AI-driven analysis (needs scores + events)
    4. STRATEGY: Synthesize final strategy (needs all results)

    Args:
        state: Current research state.

    Returns:
        Dict with next_agent name and routing reason.
    """
    next_agent = state.get("next_agent", "")

    # If state specifies next agent, follow it
    if next_agent and next_agent in AGENT_ORDER:
        return {"next_agent": next_agent, "reason": f"Scheduled: {next_agent}"}

    # Determine which agents have completed their work
    has_news = bool(state.get("scored_news"))
    has_quant = bool(state.get("quant_scores"))
    has_risk = bool(state.get("risk_assessments"))
    has_research = bool(state.get("fundamental_scores") and state.get("timing_scores"))
    has_strategy = bool(state.get("strategies"))

    # Route based on completion status
    if not has_news:
        return {"next_agent": "news", "reason": "News collection needed first"}
    elif not has_quant:
        return {"next_agent": "quant", "reason": "Quantitative scoring needed"}
    elif not has_risk:
        return {"next_agent": "risk", "reason": "Risk assessment needed"}
    elif not has_research:
        return {"next_agent": "research", "reason": "Fundamental analysis needed (depends on scores + events)"}
    elif not has_strategy:
        return {"next_agent": "strategy", "reason": "Strategy synthesis needed (depends on all results)"}
    else:
        return {"next_agent": "done", "reason": "All agents completed"}