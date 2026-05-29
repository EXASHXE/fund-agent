"""Workflow context builder for report DCA rows, settlement rows, and top news."""
from __future__ import annotations

from datetime import date, timedelta

from src.infra.config.shared import effective_report_date, today as shared_today


def build_workflow_context(config, holdings_data, news_data=None, portfolio_risk_matrix=None):
    from legacy.engine.calendar import is_trade_day
    from legacy.engine.calculator import _settlement_date
    from legacy.engine.events import resolve_nav_date, _effective_trade_date

    run_date = shared_today()
    report_date = effective_report_date()
    is_run_trade_day = is_trade_day(run_date)
    is_report_current = report_date == run_date
    is_trade_report = is_trade_day(report_date)
    is_actual_trade_report = is_run_trade_day and is_report_current
    by_fund = (holdings_data or {}).get("by_fund", {})

    dca_rows = []
    for holding in config.holdings:
        if not holding.dca or not holding.dca.enabled:
            continue

        scheduled_date = holding.dca.start_date
        status = "今日执行" if scheduled_date == run_date and is_actual_trade_report else "等待下次"
        if scheduled_date and scheduled_date < run_date:
            status = "待滚动/待确认"
        trade_date = None
        nav_date = None
        settle_date = None
        if scheduled_date:
            trade_date = _effective_trade_date(scheduled_date, after_1500=False)
            nav_date = resolve_nav_date(
                scheduled_date,
                after_1500=False,
                settle_delay=holding.settle_delay,
            )
            settle_date = _settlement_date(trade_date, holding.settle_delay)

        dca_rows.append({
            "code": holding.code,
            "name": holding.name,
            "frequency": holding.dca.frequency.value,
            "amount": holding.dca.amount,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else "",
            "status": status,
            "trade_date": trade_date.isoformat() if trade_date else "",
            "nav_date": nav_date.isoformat() if nav_date else "",
            "settle_date": settle_date.isoformat() if settle_date else "",
            "earnings_visible_after": f"{settle_date.isoformat()} 21:30后" if settle_date else "",
        })

    settlement_rows = []
    for fund in (holdings_data or {}).get("funds", []):
        detail = by_fund.get(fund["code"], {})
        pending_events = [
            event for event in detail.get("engine_events", [])
            if event.get("type") == "BUY" and event.get("status") == "PENDING"
        ]
        settle_delay = int(detail.get("settle_delay", 1) or 1)
        next_settle = min(
            (event.get("settle_date", "") for event in pending_events),
            default="",
        )
        settlement_rows.append({
            "code": fund["code"],
            "name": fund["name"],
            "fund_type": str(getattr(detail.get("fund_type", ""), "value", detail.get("fund_type", ""))),
            "current_nav": detail.get("current_nav", 0),
            "nav_date": detail.get("nav_date", ""),
            "shares": detail.get("total_shares", 0),
            "simulated_shares": detail.get("simulated_shares", 0),
            "pending_amount": detail.get("pending_amount", 0),
            "pending_events": pending_events,
            "next_settle_date": next_settle,
            "nav_status": (
                "披露日期早于口径日"
                if detail.get("nav_date", "") and detail.get("nav_date", "") < report_date.isoformat()
                else "口径日已覆盖"
            ),
            "settle_delay": settle_delay,
            "settlement_status": (
                "有待确认交易"
                if pending_events or detail.get("pending_amount", 0) > 0
                else "已确认"
            ),
        })

    top_news = []
    for item in news_data or []:
        eligible_news = [
            news for news in item.get("news_list", [])
            if news.get("date") and news.get("date") <= report_date.isoformat()
        ]
        if eligible_news:
            top_news.append({
                "code": item.get("fund_code", ""),
                "name": item.get("fund_name", ""),
                "sentiment": item.get("sentiment_mean", 0.5),
                "headline": eligible_news[0].get("title", ""),
                "date": eligible_news[0].get("date", ""),
            })

    return {
        "run_date": run_date.isoformat(),
        "report_date": report_date.isoformat(),
        "run_is_trade_day": is_run_trade_day,
        "is_trade_day": is_trade_report,
        "mode": "current_trade_day" if is_trade_report else "prior_settlement",
        "mode_reason": "当前交易日数据已过分界点" if is_trade_report else "使用上一口径日数据",
        "dca_rows": dca_rows,
        "settlement_rows": settlement_rows,
        "top_news": top_news[:8],
        "portfolio_risk_matrix": portfolio_risk_matrix or {},
    }
