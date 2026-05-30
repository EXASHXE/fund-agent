"""Optional reference planner example.

External hosts are expected to provide their own planner/orchestrator. This file
is not a required entrypoint for the skill pack.
"""


def simple_skill_order(objective: str) -> list[str]:
    order = ["fund_analysis"]
    lowered = objective.lower()
    if "news" in lowered or "review" in lowered:
        order.append("news_research")
    if "sentiment" in lowered or "review" in lowered:
        order.append("sentiment_analysis")
    order.extend(["thesis_generation", "decision_support"])
    return order
