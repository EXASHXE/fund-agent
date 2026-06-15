"""Section registry — SECTION_ORDER, titles, and builder lookup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("executive_summary", "Executive summary"),
    ("portfolio_snapshot", "Portfolio snapshot"),
    ("pnl_and_cost_basis", "PnL and cost basis"),
    ("position_contribution", "Position contribution"),
    ("allocation_and_exposure", "Allocation and exposure"),
    ("risk_flags", "Risk flags"),
    ("performance_and_nav", "Performance and NAV"),
    ("benchmark_and_peer", "Benchmark and peer"),
    ("benchmark_divergence", "Benchmark divergence"),
    ("factor_and_style", "Factor and style"),
    ("factor_analysis", "Factor analysis"),
    ("fees_and_redemption", "Fees and redemption"),
    ("manager_and_fund_profile", "Manager and fund profile"),
    ("dca_and_trade_budget", "DCA and trade budget"),
    ("professional_diagnostics", "Professional diagnostics"),
    ("profit_protection", "Profit protection"),
    ("right_side_confirmation", "Right-side confirmation"),
    ("event_hype_failure", "Event hype failure"),
    ("news_and_events", "News and events"),
    ("cash_deployment", "Cash deployment"),
    ("evidence_status", "Evidence status"),
    ("action_watchlist", "Action watchlist"),
    ("missing_data", "Missing data"),
    ("suggested_next_checks", "Suggested next checks"),
    ("uncertainty_note", "Uncertainty note"),
    ("rebalance_plan", "Rebalance plan"),
    ("research_query_plan", "Research query plan"),
    ("data_completeness_and_limitations", "Data completeness and limitations"),
    ("evidence_appendix", "Evidence appendix"),
)

ZH_CN_SECTION_TITLES: dict[str, str] = {
    "executive_summary": "组合概览",
    "portfolio_snapshot": "持仓快照",
    "pnl_and_cost_basis": "收益与成本",
    "position_contribution": "仓位贡献",
    "allocation_and_exposure": "配置与暴露",
    "risk_flags": "风险提示",
    "performance_and_nav": "净值与表现",
    "benchmark_and_peer": "基准与同类",
    "benchmark_divergence": "基准偏离",
    "factor_and_style": "风格因子",
    "factor_analysis": "因子分析",
    "fees_and_redemption": "赎回费与持有期",
    "manager_and_fund_profile": "基金资料与经理",
    "dca_and_trade_budget": "定投与交易预算",
    "professional_diagnostics": "专业诊断",
    "profit_protection": "盈利保护",
    "right_side_confirmation": "右侧确认",
    "event_hype_failure": "事件催化检验",
    "news_and_events": "新闻与事件",
    "cash_deployment": "现金与低风险仓位",
    "evidence_status": "证据状态",
    "action_watchlist": "操作观察清单",
    "missing_data": "缺失数据",
    "suggested_next_checks": "后续检查项",
    "uncertainty_note": "不确定性说明",
    "rebalance_plan": "再平衡分析",
    "research_query_plan": "研究查询计划",
    "data_completeness_and_limitations": "数据限制",
    "evidence_appendix": "证据附录",
}

VALID_STATUSES = {"OK", "PARTIAL", "MISSING"}


@dataclass(frozen=True)
class SectionBuilder:
    """Registry entry for a report section builder."""

    section_id: str
    title_en: str
    title_zh: str
    build_fn: Callable[..., dict[str, Any]] | None = None
    required_keys: tuple[str, ...] = ("id", "title", "status")


# Build registry from SECTION_ORDER
section_registry: dict[str, SectionBuilder] = {}
for _sid, _title_en in SECTION_ORDER:
    section_registry[_sid] = SectionBuilder(
        section_id=_sid,
        title_en=_title_en,
        title_zh=ZH_CN_SECTION_TITLES.get(_sid, _title_en),
    )
