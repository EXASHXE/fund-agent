"""Strategy engine: structured investment advice generation.

Replaces static "持有观察" with regime-aware StrategyAdvice using a state machine.

Modules:
    schemas.py      — StrategyAction, StrategyState, StrategyAdvice data models
    stop_logic.py   — Regime-aware stop-loss and take-profit thresholds
    state_machine.py — Deterministic strategy state transitions
    advisor.py      — Generates StrategyAdvice from scores, KG, and events
    engine.py       — Top-level orchestrator combining ScoreEngine + StrategyAdvisor
"""
from src.strategy.schemas import StrategyAction, StrategyState, StrategyAdvice
from src.strategy.stop_logic import StopLogic
from src.strategy.state_machine import StateMachine
from src.strategy.advisor import StrategyAdvisor
from src.strategy.engine import StrategyEngine
from src.strategy.models import ActionPlan, StrategyDecision, TriggerPoint

__all__ = [
    "StrategyAction", "StrategyState", "StrategyAdvice",
    "StopLogic", "StateMachine", "StrategyAdvisor", "StrategyEngine",
    "ActionPlan", "StrategyDecision", "TriggerPoint",
]
