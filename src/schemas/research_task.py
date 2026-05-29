"""ResearchTask schema — typed input contract for fund research workflows.

Defines the input contract for initiating a fund research analysis.
JSON-serializable via dataclasses.asdict() with camelCase key mapping.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

_CAMEL_MAP: dict[str, str] = {
    "task_id": "taskId",
    "user_id": "userId",
    "portfolio": "portfolio",
    "fund_universe": "fundUniverse",
    "as_of_date": "asOfDate",
    "objective": "objective",
    "constraints": "constraints",
    "risk_profile": "riskProfile",
    "time_horizon": "timeHorizon",
}
_SNAKE_MAP: dict[str, str] = {v: k for k, v in _CAMEL_MAP.items()}


@dataclass
class ResearchTask:
    """Typed input contract for a fund research analysis request.

    Attributes:
        task_id: Unique identifier for this research task.
        user_id: Optional user identifier requesting the analysis.
        portfolio: The portfolio configuration dict (fund codes, weights, etc.).
        fund_universe: List of fund codes to consider in the analysis.
        as_of_date: Date string for the analysis reference date.
        objective: Natural language description of the research objective.
        constraints: Dict of analysis constraints (budget, risk limits, etc.).
        risk_profile: Risk profile string (e.g. "conservative", "moderate", "aggressive").
        time_horizon: Investment time horizon (e.g. "1 year", "6 months").
    """

    task_id: str
    user_id: str = ""
    portfolio: dict = field(default_factory=dict)
    fund_universe: list[str] = field(default_factory=list)
    as_of_date: str = ""
    objective: str = ""
    constraints: dict = field(default_factory=dict)
    risk_profile: str = "moderate"
    time_horizon: str = "1 year"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict with camelCase keys.

        Converts snake_case field names to camelCase for API compatibility.
        """
        raw = asdict(self)
        return {_CAMEL_MAP.get(k, k): v for k, v in raw.items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchTask:
        """Deserialize from a dict (camelCase or snake_case keys) back to ResearchTask.

        Accepts both camelCase keys (from to_dict output) and snake_case keys
        for flexibility.
        """
        mapped = {}
        for k, v in data.items():
            snake_key = _SNAKE_MAP.get(k, k)
            if snake_key in _CAMEL_MAP:
                mapped[snake_key] = v
            else:
                mapped[k] = v
        return cls(**mapped)
