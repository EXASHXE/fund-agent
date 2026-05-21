"""Operation advice engine."""
from typing import Dict


def build_operation_advice(score: Dict, trend_matrix: Dict, position_context: Dict = None) -> Dict:
    """Build a structured operation suggestion from score, trend and position."""
    position_context = position_context or {}
    composite = float(score.get("final_score", score.get("composite_score", 50)) or 50)
    completeness = score.get("data_completeness", "C")
    short = (trend_matrix or {}).get("short_term", {})
    direction = short.get("direction", "flat")
    trend_score = float(short.get("score", 0.5) or 0.5)
    trend_conf = float(short.get("confidence", 0.5) or 0.5)

    total_value = float(position_context.get("total_value", 0) or 0)
    current_weight = float(position_context.get("current_weight", 0) or 0)
    pending_amount = float(position_context.get("pending_amount", 0) or 0)
    current_value = float(position_context.get("current_value", 0) or 0)
    is_qdii = bool(position_context.get("is_qdii"))

    target_weight = _target_weight(composite, direction, completeness)
    adjust_amount = round((target_weight - current_weight) * total_value, 2) if total_value else 0.0
    action = "hold"
    triggers = []

    if completeness == "D":
        action = "observe"
        target_weight = min(target_weight, current_weight)
        adjust_amount = 0.0
        triggers.append("数据完整度 D，禁止新增仓位")
    elif is_qdii and pending_amount >= max(500.0, current_value * 0.5):
        action = "hold_wait"
        adjust_amount = 0.0
        triggers.append("QDII pending 较高，等待确认后再新增")
    elif composite < 50 or direction == "down":
        action = "reduce" if current_weight > target_weight else "pause_dca"
        adjust_amount = min(0.0, adjust_amount)
        triggers.append("评分偏弱或短期趋势下行")
    elif composite >= 70 and direction == "up" and adjust_amount > max(300.0, total_value * 0.02):
        action = "buy"
        triggers.append("高评分且短期趋势上行，当前仓位低于目标")
    elif composite >= 60 and trend_score >= 0.55:
        action = "hold"
        adjust_amount = 0.0 if abs(adjust_amount) < max(300.0, total_value * 0.02) else adjust_amount
        triggers.append("评分和趋势处于可持有区间")
    else:
        action = "hold"
        adjust_amount = 0.0
        triggers.append("趋势信号中性，维持观察")

    confidence = _clip01((composite / 100.0) * 0.45 + trend_conf * 0.45 + _completeness_conf(completeness) * 0.10)
    return {
        "action": action,
        "target_weight": round(target_weight, 4),
        "adjust_amount": round(adjust_amount, 2),
        "confidence": round(confidence, 4),
        "triggers": triggers,
    }


def _target_weight(composite: float, direction: str, completeness: str) -> float:
    if completeness in ("C", "D"):
        base = 0.08
    elif composite >= 80:
        base = 0.22
    elif composite >= 70:
        base = 0.18
    elif composite >= 60:
        base = 0.14
    elif composite >= 50:
        base = 0.10
    else:
        base = 0.05
    if direction == "up":
        base += 0.02
    elif direction == "down":
        base -= 0.03
    return max(0.02, min(0.25, base))


def _completeness_conf(completeness: str) -> float:
    return {"A": 0.95, "B": 0.82, "C": 0.55, "D": 0.2}.get(completeness, 0.6)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))
