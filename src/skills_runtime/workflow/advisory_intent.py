"""Deterministic advisory intent classifier.

Classifies a user request into one or more advisory intents using
explicit host-provided intent hints first, then deterministic keyword
matching on the user_question text.

No LLM. No network. No randomness.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AdvisoryIntent(StrEnum):
    """Advisory intent taxonomy for fund-agent v1.5.1."""

    REPORT_ONLY = "REPORT_ONLY"
    FORMAL_TRADE_DECISION = "FORMAL_TRADE_DECISION"
    SOFT_ACTION_ADVICE = "SOFT_ACTION_ADVICE"
    PROFIT_PROTECTION = "PROFIT_PROTECTION"
    DRAWDOWN_RESPONSE = "DRAWDOWN_RESPONSE"
    RIGHT_SIDE_CONFIRMATION = "RIGHT_SIDE_CONFIRMATION"
    SHORT_HOLDING_FEE_CHECK = "SHORT_HOLDING_FEE_CHECK"
    PORTFOLIO_REBALANCE = "PORTFOLIO_REBALANCE"
    CASH_DEPLOYMENT = "CASH_DEPLOYMENT"
    OVERLAP_CONCENTRATION_CHECK = "OVERLAP_CONCENTRATION_CHECK"
    DCA_REVIEW = "DCA_REVIEW"
    RISK_REDUCTION = "RISK_REDUCTION"
    WATCHLIST_ONLY = "WATCHLIST_ONLY"


INTENT_KEYWORD_RULES: dict[AdvisoryIntent, list[str]] = {
    AdvisoryIntent.FORMAL_TRADE_DECISION: [
        "买入", "卖出", "减仓", "加仓", "正式决策",
        "给我决策", "正式操作", "今天卖出", "今天买入",
        "执行", "下单",
    ],
    AdvisoryIntent.SOFT_ACTION_ADVICE: [
        "操作建议", "怎么操作", "怎么处理", "该怎么办",
        "要不要动", "如何应对", "怎么调整", "怎么应对",
    ],
    AdvisoryIntent.PROFIT_PROTECTION: [
        "盈利很多", "止盈", "落袋", "本金回收",
        "赚了很多", "涨了很多", "利润", "获利",
        "赎回利润", "拿回本金",
    ],
    AdvisoryIntent.DRAWDOWN_RESPONSE: [
        "跌了", "回撤", "要不要补", "要不要割",
        "亏损", "跌穿", "大幅下跌", "暴跌",
        "要不要跑", "深度套牢",
    ],
    AdvisoryIntent.RIGHT_SIDE_CONFIRMATION: [
        "右侧", "企稳", "反弹确认", "是否见底",
        "止跌", "底部", "反转确认",
        "能不能抄底",
    ],
    AdvisoryIntent.SHORT_HOLDING_FEE_CHECK: [
        "7天", "手续费", "赎回费", "不足7天",
        "持有期", "费率", "没满", "未满",
        "短期赎回",
    ],
    AdvisoryIntent.CASH_DEPLOYMENT: [
        "现金", "债券仓位", "余额宝", "部署",
        "还能投哪", "资金闲置", "现金占比",
        "闲置", "现金管理", "闲钱", "余钱",
        "货币基金占比",
    ],
    AdvisoryIntent.OVERLAP_CONCENTRATION_CHECK: [
        "重合", "持仓重复", "QDII", "AI",
        "美股科技", "集中度", "相关性",
        "有没有重复", "是否太多", "同一个行业",
        "分散", "重合度", "重叠",
    ],
    AdvisoryIntent.DCA_REVIEW: [
        "定投", "DCA", "扣款", "暂停定投",
        "继续定投", "修改定投",
    ],
    AdvisoryIntent.RISK_REDUCTION: [
        "风险太大", "降风险", "保守", "减配",
        "过于集中", "波动太大", "降低仓位",
    ],
    AdvisoryIntent.REPORT_ONLY: [
        "分析", "报告", "怎么看", "情况怎么样",
        "看一下", "帮忙看看",
    ],
    AdvisoryIntent.PORTFOLIO_REBALANCE: [
        "调整仓位", "配置", "平衡", "再平衡",
        "调仓", "换仓", "换基金",
    ],
    AdvisoryIntent.WATCHLIST_ONLY: [
        "观察", "关注", "继续看", "跟踪",
        "等机会",
    ],
}

DEFAULT_INTENT = AdvisoryIntent.REPORT_ONLY

HOST_INTENT_ALIASES: dict[str, AdvisoryIntent] = {
    "report_only": AdvisoryIntent.REPORT_ONLY,
    "formal_reduce": AdvisoryIntent.FORMAL_TRADE_DECISION,
    "formal_buy": AdvisoryIntent.FORMAL_TRADE_DECISION,
    "formal_trade": AdvisoryIntent.FORMAL_TRADE_DECISION,
    "formal_sell": AdvisoryIntent.FORMAL_TRADE_DECISION,
    "formal_decision": AdvisoryIntent.FORMAL_TRADE_DECISION,
    "soft_action": AdvisoryIntent.SOFT_ACTION_ADVICE,
    "soft_advice": AdvisoryIntent.SOFT_ACTION_ADVICE,
    "action_advice": AdvisoryIntent.SOFT_ACTION_ADVICE,
    "profit_protection": AdvisoryIntent.PROFIT_PROTECTION,
    "drawdown_response": AdvisoryIntent.DRAWDOWN_RESPONSE,
    "right_side": AdvisoryIntent.RIGHT_SIDE_CONFIRMATION,
    "fee_check": AdvisoryIntent.SHORT_HOLDING_FEE_CHECK,
    "cash_deployment": AdvisoryIntent.CASH_DEPLOYMENT,
    "overlap_check": AdvisoryIntent.OVERLAP_CONCENTRATION_CHECK,
    "dca_review": AdvisoryIntent.DCA_REVIEW,
    "risk_reduction": AdvisoryIntent.RISK_REDUCTION,
    "watchlist": AdvisoryIntent.WATCHLIST_ONLY,
    "rebalance": AdvisoryIntent.PORTFOLIO_REBALANCE,
}


def classify_advisory_intent(
    *,
    host_intent_hint: str | None = None,
    user_question: str | None = None,
    requested_action: str | None = None,
) -> list[str]:
    """Classify a user request into one or more advisory intents.

    Priority:
    1. If `host_intent_hint` maps to a known alias, use it as the primary intent.
    2. If `host_intent_hint` is a raw intent string, use it directly.
    3. Then apply deterministic keyword matching on `user_question`.
    4. If `requested_action` is active (BUY/SELL/REDUCE/INCREASE), add FORMAL_TRADE_DECISION.
    5. If no intent matched, default to REPORT_ONLY.
    """
    intents: list[str] = []

    # 1. Host-provided intent hint
    if host_intent_hint:
        alias_key = host_intent_hint.strip().lower()
        if alias_key in HOST_INTENT_ALIASES:
            intents.append(HOST_INTENT_ALIASES[alias_key].value)
        else:
            # Check if it's already a valid enum value
            try:
                AdvisoryIntent(host_intent_hint.strip())
                intents.append(host_intent_hint.strip())
            except ValueError:
                pass

    # 2. Requested action implies FORMAL_TRADE_DECISION
    active_actions = {"BUY", "SELL", "INCREASE", "REDUCE"}
    if requested_action and requested_action.strip().upper() in active_actions:
        _add_if_missing(intents, AdvisoryIntent.FORMAL_TRADE_DECISION.value)

    # 3. Keyword matching on user_question
    if user_question:
        matched_intents: list[str] = _match_keywords(user_question)
        for intent in matched_intents:
            _add_if_missing(intents, intent)

    # 4. If user_question is about analysis/report without action, ensure REPORT_ONLY
    if user_question and AdvisoryIntent.FORMAL_TRADE_DECISION.value not in intents:
        _add_if_missing(intents, AdvisoryIntent.REPORT_ONLY.value)

    # 5. Default fallback
    if not intents:
        intents.append(AdvisoryIntent.REPORT_ONLY.value)

    return intents


def is_report_only(intents: list[str]) -> bool:
    """Return True if the intents describe a report-only (non-formal) scenario.

    SOFT_ACTION_ADVICE alone does not imply formal decision — it means the user
    wants guidance, not execution.
    """
    return AdvisoryIntent.FORMAL_TRADE_DECISION.value not in intents


def is_formal_decision_requested(intents: list[str]) -> bool:
    """Return True if FORMAL_TRADE_DECISION is in the intents.

    SOFT_ACTION_ADVICE does NOT count as formal. Only explicit trade
    language (买入/卖出/减仓/加仓/下单/正式决策) triggers formal path.
    """
    return AdvisoryIntent.FORMAL_TRADE_DECISION.value in intents


def is_soft_advice_only(intents: list[str]) -> bool:
    """Return True if user only requested soft advice, not a formal decision."""
    return (
        AdvisoryIntent.SOFT_ACTION_ADVICE.value in intents
        and AdvisoryIntent.FORMAL_TRADE_DECISION.value not in intents
    )


def intent_requires_decision_support(intents: list[str]) -> bool:
    """Return True if any intent implies decision_support should be called.

    Only FORMAL_TRADE_DECISION requires decision_support.
    SOFT_ACTION_ADVICE without formal trade intent does not.
    """
    return is_formal_decision_requested(intents)


def get_direct_answer_hints(intents: list[str]) -> list[str]:
    """Return short advisory hints based on intents for composing direct_answer bullets."""
    hints: list[str] = []

    if AdvisoryIntent.REPORT_ONLY.value in intents:
        hints.append("report_only_flow")
    if AdvisoryIntent.FORMAL_TRADE_DECISION.value in intents:
        hints.append("formal_trade_requested")
    if AdvisoryIntent.SOFT_ACTION_ADVICE.value in intents:
        hints.append("soft_action_advice")
    if AdvisoryIntent.PROFIT_PROTECTION.value in intents:
        hints.append("profit_protection_concern")
    if AdvisoryIntent.DRAWDOWN_RESPONSE.value in intents:
        hints.append("drawdown_concern")
    if AdvisoryIntent.RIGHT_SIDE_CONFIRMATION.value in intents:
        hints.append("right_side_check")
    if AdvisoryIntent.SHORT_HOLDING_FEE_CHECK.value in intents:
        hints.append("fee_redemption_concern")
    if AdvisoryIntent.CASH_DEPLOYMENT.value in intents:
        hints.append("cash_deployment_concern")
    if AdvisoryIntent.OVERLAP_CONCENTRATION_CHECK.value in intents:
        hints.append("overlap_concentration_concern")
    if AdvisoryIntent.DCA_REVIEW.value in intents:
        hints.append("dca_review_concern")
    if AdvisoryIntent.RISK_REDUCTION.value in intents:
        hints.append("risk_reduction_concern")
    if AdvisoryIntent.WATCHLIST_ONLY.value in intents:
        hints.append("watchlist_only_flow")

    return hints


def _match_keywords(question: str) -> list[str]:
    """Deterministic keyword matching on user_question."""
    matched = []
    question_lower = question.lower()

    for intent, keywords in INTENT_KEYWORD_RULES.items():
        for kw in keywords:
            if kw.lower() in question_lower:
                matched.append(intent.value)
                break

    return matched


def _add_if_missing(lst: list[str], value: str) -> None:
    """Append value if not already in list."""
    if value not in lst:
        lst.append(value)
