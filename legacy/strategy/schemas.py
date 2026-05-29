"""Strategy schemas: data models for strategy advice and state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StrategyAction(Enum):
    """Investment actions that the strategy engine can recommend."""
    HOLD = "hold"
    ADD = "add"
    REDUCE = "reduce"
    SWITCH = "switch"
    WAIT = "wait"
    STOP_LOSS = "stop_loss"


class StrategyState(Enum):
    """States in the strategy state machine."""
    WAIT = "wait"
    HOLD = "hold"
    ADD = "add"
    REDUCE = "reduce"
    STOP_LOSS = "stop_loss"


@dataclass
class StrategyAdvice:
    """Structured investment advice produced by the strategy engine.

    Replaces the static "持有观察" output with regime-aware, evidence-based advice.
    """
    action: StrategyAction
    confidence: float                    # 0.0-1.0
    risk_level: str                      # "low", "medium", "high", "extreme"
    reasons: list[str]                   # Evidence chain
    trigger_events: list[str]            # What to watch for state change
    position_suggestion: str             # "持有" / "加仓10%" / "减仓至3%"
    time_horizon: str                    # "short", "medium", "long"
    stop_loss_pct: float | None = None   # Regime-aware stop loss
    take_profit_pct: float | None = None  # Regime-aware take profit
    state: StrategyState = StrategyState.WAIT
    valid_transitions: dict = field(default_factory=dict)  # State → [possible next states]
