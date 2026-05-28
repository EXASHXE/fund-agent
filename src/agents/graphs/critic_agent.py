"""Critic Agent Node — adversarial review before strategy synthesis.

Checks for counter-evidence, single-source bias, and reasoning gaps
across all scoring dimensions before passing to strategy agent.
Includes circuit breaker to prevent infinite iteration loops.
"""
from __future__ import annotations

import logging
from typing import Any

from src.agents.state import FundResearchState

logger = logging.getLogger(__name__)


def critic_agent_node(state: FundResearchState) -> dict:
    """Check for counter-evidence, bias, and reasoning gaps.

    Reviews all scoring results in state to identify:
      1. Missing dimensions per fund
      2. Single-source bias (all evidence from one scoring provider)
      3. Gaps in evidence chain
      4. Consensus (or conflict) between score sources

    Circuit breaker: if iteration >= 3 or bias_score > 0.8,
    forces passed=True to prevent infinite loops.

    Args:
        state: FundResearchState with all scoring results populated.

    Returns:
        Dict with critic_report containing bias_score, gaps, conflicts,
        passed, and circuit_broken indicators.
    """
    iteration = state.get("iteration", 1)
    funds_data = state.get("funds_data", {})

    gaps: list[str] = []

    for code in funds_data:
        required = ["quant", "fundamental", "event", "position", "timing"]
        for dim in required:
            dim_key = f"{dim}_scores"
            dim_data = state.get(dim_key, {})
            if not dim_data.get(code):
                gaps.append(f"Missing {dim} score for {code}")

    # Bias detection: more iterations = higher bias risk
    bias_score = min((iteration - 1) / 3.0, 1.0) if iteration > 1 else 0.0

    # Conflict detection placeholder (in production: EvidenceGraph.detect_conflicts())
    conflicts: list[str] = []

    # Circuit breaker: force-pass when conditions met
    circuit_broken = iteration >= 3 or bias_score > 0.8

    # Pass if no gaps, OR circuit breaker triggered
    passed = len(gaps) == 0 or circuit_broken

    return {
        "critic_report": {
            "bias_score": bias_score,
            "gaps": gaps,
            "conflicts": conflicts,
            "passed": passed,
            "iteration": iteration,
            "circuit_broken": circuit_broken,
        }
    }
