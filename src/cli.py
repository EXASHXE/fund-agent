"""
统一 CLI 入口。

用法:
    python -m src.cli init [-o fund-portfolio.yaml]
    python -m src.cli import -c fund-portfolio.yaml
    python -m src.cli analyze -c fund-portfolio.yaml -o report.md
    python -m src.cli fetch -c fund-portfolio.yaml
    python -m src.cli score -o report.md
    python -m src.cli news -c fund-portfolio.yaml --days 7
    python -m src.cli recommend -c fund-portfolio.yaml --top 5
    python -m src.cli diagnose 008253
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta

from src.config.shared import effective_report_date, today as _shared_today, now as _shared_now, dca_effective_date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_init(args):
    """生成示例 YAML 配置文件"""
    from src.config.loader import generate_sample_yaml
    output = args.output or "fund-portfolio.yaml"
    generate_sample_yaml(output)


def cmd_import(args):
    """导入持仓配置到数据库"""
    from src.config.loader import load_portfolio_config, import_to_database
    config = load_portfolio_config(args.config)
    print(f"加载配置: {len(config.holdings)} 只基金, {len(config.watchlist)} 只自选")
    import_to_database(config)
    print("导入完成。")


def request_agent_keywords_inline(
    holding_codes: list,
    fund_profiles: list,
) -> dict | None:
    """标准 Agent 关键词请求回调。上层 runtime 可 monkey-patch 此函数。

    返回格式: {"fund_code": ["kw1", "kw2", ...], ...}
    若 Agent 不可用（纯 CLI），返回 None 触发降级兜底。
    """
    return None  # 默认无 Agent，降级到重仓股名+默认词


def cmd_analyze(args):
    """完整分析流程：加载配置 → 同步元数据 → 采集 → 分析 → 报告 → 保存分析快照。

    analyze 保持只读持仓配置，不在报告生成前滚动定投日期或追加买入记录。
    配置滚动由 snapshot 子命令显式执行，避免当天未结算定投污染报告口径。
    """
    from src.config.loader import load_portfolio_config, import_to_database
    from src.analysis.scorer import FundAnalyzer
    from src.analysis.correlation import compute_correlations
    from src.analysis.stress import stress_test
    from src.output.report import generate_report
    from src.db.storage import FundStorage

    config = load_portfolio_config(args.config)
    import_to_database(config)

    store = FundStorage()
    if not config.holdings:
        print("[ERROR] 无持仓数据")
        return

    codes = [h.code for h in config.holdings]
    report_date = effective_report_date()
    print(f"\n持仓基金 {len(codes)} 只: {codes}")
    print(f"报告口径日: {report_date.isoformat()}")

    print("\n[Layer 1] 数据采集...")
    print("Agent 模式: 脚本生成数据证据包；最终评分/新闻/压力测试/推荐由接入 skill 的模型判断")

    analyzer = FundAnalyzer()
    for code in codes:
        try:
            analyzer.load_fund(code)
        except Exception as e:
            print(f"  [ERROR] {code}: {e}")

    from src.news.keyword_cache import (
        CACHE_VERSION,
        default_keyword_cache_path,
        load_valid_keyword_cache,
    )
    keyword_cache_path = (
        getattr(args, "news_keyword_cache", None)
        or default_keyword_cache_path()
    )
    news_keyword_plan = load_valid_keyword_cache(keyword_cache_path, codes, today=_shared_today())
    if not news_keyword_plan:
        # 尝试 Agent inline 回调获取实时关键词
        fund_profiles = []
        for code in codes:
            fund_data = analyzer.funds.get(code, {})
            basic = fund_data.get("basic", {})
            fund_profiles.append({
                "code": code,
                "name": basic.get("name", code),
                "type": basic.get("fund_type", ""),
            })
        agent_kw = request_agent_keywords_inline(codes, fund_profiles)
        if agent_kw:
            news_keyword_plan = {
                "cache_version": CACHE_VERSION,
                "holding_codes": sorted(codes),
                "generated_at": _shared_today().isoformat(),
                "funds": {
                    code: {"keywords": agent_kw.get(code, [])}
                    for code in codes
                },
            }
        else:
            # 无 Agent：按 SKILL.md 输出关键词请求 JSON 并停止
            _write_keyword_request_and_exit(config, codes, analyzer, args.output or "report.md")
            return  # unreachable, _write_keyword_request_and_exit calls sys.exit

    # 新闻分析前置：新闻催化与情绪作为评分系统的输入证据。
    print("\n[Layer 2] 新闻采集与分析...")
    news_data = _run_news_analysis(config, analyzer, agent_news_plan=news_keyword_plan)
    news_contexts = _news_context_by_code(news_data)

    print("\n[Layer 3] 分析打分...")
    scores = []
    unscores = []
    for code in codes:
        if code in analyzer.funds:
            fund = analyzer.funds[code]
            if fund["completeness"] != "D":
                s = analyzer.score_fund(code, news_context=news_contexts.get(code))
                scores.append(s)
                print(f"  {code}: {s['composite_score']}/100 ({s['score_level_emoji']})")
            else:
                basic = fund.get("basic", {})
                unscores.append({
                    "code": code,
                    "name": basic.get("name", code),
                    "fund_name": basic.get("name", code),
                    "fund_code": code,
                    "data_completeness": "D",
                    "error": basic.get("error", "核心数据获取失败"),
                })
                print(f"  {code}: D (数据不足) — {basic.get('error', '核心数据获取失败')[:60]}")
        else:
            unscores.append({
                "code": code,
                "name": code,
                "fund_name": code,
                "fund_code": code,
                "data_completeness": "D",
                "error": "数据采集失败",
            })

    correlations = compute_correlations(analyzer.funds)
    if getattr(args, "stress", False):
        stress_results = stress_test(analyzer.funds)
        print(f"\n  压力测试: {len(stress_results)} 条风险线索")
    else:
        stress_results = []
        print("\n  [默认跳过] 压力测试（--stress 启用）")

    _attach_score_trends(store, scores)

    # 持仓分析
    holdings_data = _compute_holdings(store, config, codes, analyzer)
    _attach_trends_and_advice(scores, news_contexts, holdings_data)
    from src.analysis.portfolio_risk import build_portfolio_risk_matrix
    portfolio_risk_matrix = build_portfolio_risk_matrix(holdings_data, scores, correlations)
    workflow_context = _build_workflow_context(config, holdings_data, news_data=news_data)
    if isinstance(workflow_context, dict):
        workflow_context["portfolio_risk_matrix"] = portfolio_risk_matrix

    # 推荐（默认关闭，--recommend 启用）
    recommendations = []
    recommendation_status = "skipped" if not args.recommend else "empty"
    inter_recommendation_correlations = None
    if args.recommend:
        print("\n[推荐] 搜索推荐基金...")
        recommendations, inter_recommendation_correlations = _run_recommendations(
            news_data,
            codes,
            analyzer,
            portfolio_risk_matrix=portfolio_risk_matrix,
        )
        recommendation_status = "ok" if recommendations else "empty"

    print("\n[Layer 4] 生成报告...")
    report = generate_report(
        analyzer, scores, correlations, stress_results,
        holdings_data=holdings_data,
        news_data=news_data,
        recommendations=recommendations,
        recommendation_status=recommendation_status,
        unscores=unscores,
        workflow_context=workflow_context,
        inter_recommendation_correlations=inter_recommendation_correlations,
    )

    # 后置校验：止盈止损校准 + 合规声明追加
    from src.output.validator import post_process_report
    report = post_process_report(report, scores)

    report_path = args.output or "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存: {report_path}")

    _save_snapshot(store, scores, stress_results, correlations, holdings_data=holdings_data)
    if _should_snapshot_after_analyze(args):
        _perform_snapshot(args.config)


def _attach_score_trends(store, scores):
    """Attach previous score and peak drawdown from saved snapshots."""
    for s in scores:
        history = store.get_fund_score_history(s["fund_code"], limit=50)
        valid_scores = [
            h.get("composite_score")
            for h in history
            if h.get("composite_score") is not None
        ]
        if not valid_scores:
            s["previous_score"] = None
            s["score_delta"] = None
            s["peak_score"] = s["composite_score"]
            s["drop_from_peak"] = 0
            continue

        previous = valid_scores[0]
        peak = max(valid_scores + [s["composite_score"]])
        s["previous_score"] = previous
        s["score_delta"] = s["composite_score"] - previous
        s["peak_score"] = peak
        s["drop_from_peak"] = peak - s["composite_score"]


def _news_context_by_code(news_data):
    """Build compact per-fund news context for scoring and agent review."""
    contexts = {}
    for item in news_data or []:
        code = item.get("fund_code")
        if not code:
            continue
        catalyst_news = item.get("catalyst_news") or []
        top_catalysts = sorted(
            catalyst_news,
            key=lambda n: abs((n.get("catalyst") or {}).get("weighted_score", 0)),
            reverse=True,
        )[:5]
        contexts[code] = {
            "fund_code": code,
            "fund_name": item.get("fund_name", code),
            "status": item.get("status", ""),
            "news_count": item.get("news_count", 0),
            "sentiment_mean": item.get("sentiment_mean", 0.5),
            "daily_aggregates": (item.get("daily_aggregates") or [])[-5:],
            "brief": item.get("brief") or {},
            "news_evaluation": item.get("news_evaluation") or {},
            "top_catalysts": [
                {
                    "title": n.get("title", "")[:120],
                    "date": n.get("date", ""),
                    "event_type": (n.get("catalyst") or {}).get("event_type", ""),
                    "weighted_score": (n.get("catalyst") or {}).get("weighted_score", 0),
                    "relevance": (n.get("catalyst") or {}).get("relevance", 0),
                }
                for n in top_catalysts
            ],
        }
    return contexts


def _attach_trends_and_advice(scores, news_contexts, holdings_data):
    """Attach trend forecasts and operation advice to scored funds."""
    from src.decision.engine import build_operation_advice
    from src.forecast.engine import build_trend_matrix

    total_value = (holdings_data or {}).get("total_value", 0) or 0
    by_fund = (holdings_data or {}).get("by_fund", {}) or {}
    for score in scores:
        code = score.get("fund_code")
        trend = build_trend_matrix(score, news_contexts.get(code, {}))
        detail = by_fund.get(code, {}) or {}
        current_value = float(detail.get("current_value", 0) or 0)
        position_context = {
            "current_value": current_value,
            "total_value": total_value,
            "current_weight": current_value / total_value if total_value else 0.0,
            "pending_amount": float(detail.get("pending_amount", 0) or 0),
            "is_qdii": int(detail.get("settle_delay", 1) or 1) >= 2 or "QDII" in str(score.get("fund_type", "")).upper(),
            "dca_enabled": bool(detail.get("dca_enabled")),
        }
        score["trend_matrix"] = trend
        score["operation_advice"] = build_operation_advice(score, trend, position_context)


def _compute_holdings(store, config, codes, analyzer=None):
    """计算持仓分析数据 — 使用事件驱动引擎（支持 QDII T+2 + 校准 3% 阈值）。

    流程：交易日历 → 事件生成 → 净值匹配(含 settle_delay) → XIRR 计算 → 校准平账。
    """
    from src.engine.events import generate_events
    from src.engine.calculator import compute_fund
    from src.analysis.holdings import portfolio_summary
    from src.db.database import get_session

    session = get_session()
    today = effective_report_date()
    dca_today = dca_effective_date()  # 10:00 前当日定投未执行
    settle_today = _shared_today()  # 结算 PENDING 判断用实际日期，不受报告分界影响
    analyses = []
    calibration_warnings = []
    ledger_warnings = []

    for code in codes:
        try:
            holding_config = next((h for h in config.holdings if h.code == code), None)
            if not holding_config:
                continue

            fund = store.get_fund(code) or {
                "id": None,
                "code": code,
                "name": holding_config.name or code,
            }
            purchases = [
                {
                    "date": p.date,
                    "amount": p.amount,
                    "nav": p.nav,
                    "after_1500": p.after_1500,
                }
                for p in holding_config.purchases
            ]

            dca_strategy = None
            if holding_config and holding_config.dca and holding_config.dca.enabled:
                d = holding_config.dca
                dca_strategy = {
                    "enabled": True,
                    "frequency": d.frequency.value,
                    "amount": d.amount,
                    "start_date": d.start_date,
                    "day_of_week": d.day_of_week,
                }

            configured_fee_rate = getattr(holding_config, 'fee_rate', None)
            fee_rate = float(0.0015 if configured_fee_rate is None else configured_fee_rate)
            configured_settle_delay = getattr(holding_config, 'settle_delay', None)
            settle_delay = int(1 if configured_settle_delay is None else configured_settle_delay)

            calibrations = []
            if holding_config and hasattr(holding_config, 'calibrations'):
                for c in holding_config.calibrations:
                    calibrations.append({
                        "date": c.cal_date, "actual_shares": c.actual_shares,
                    })

            nav_map = {}
            current_nav = 1.0
            last_nav_date = None
            if analyzer and code in analyzer.funds:
                nav_df = analyzer.funds[code].get("nav")
                if nav_df is not None and hasattr(nav_df, 'iterrows') and len(nav_df) > 0:
                    for idx, row in nav_df.iterrows():
                        d = idx.date() if hasattr(idx, 'date') else idx
                        nav_val = float(row.get("单位净值", 0))
                        if nav_val:
                            nav_map[d] = nav_val
                    if nav_map:
                        last_nav_date = max(nav_map.keys())
                        current_nav = nav_map[last_nav_date]

            if not nav_map:
                from src.db.database import get_nav_history
                if fund.get("id"):
                    nav_list = get_nav_history(session, fund["id"])
                    for n in nav_list:
                        nav_map[n.date] = float(n.nav)
                    if nav_map:
                        last_nav_date = max(nav_map.keys())
                        current_nav = nav_map[last_nav_date]

            events = generate_events(purchases, dca_strategy, calibrations, dca_today)

            result = compute_fund(events, nav_map, fee_rate, settle_delay, settle_today)

            display_value = result["current_asset"]
            display_profit = result["confirmed_pnl"]
            display_return_pct = result["confirmed_return_pct"]
            purchase_amount = round(sum(float(p.get("amount", 0) or 0) for p in purchases), 2)
            total_cost = result["total_cost"]
            total_shares = result["total_shares"]
            avg_cost = result["avg_cost"]
            pending_amount = result["pending_amount"]

            explicit_shares = float(getattr(holding_config, "shares", 0) or 0) if holding_config else 0.0
            explicit_avg_cost = float(getattr(holding_config, "avg_cost", 0) or 0) if holding_config else 0.0
            ledger_warning = None
            if explicit_shares > 0 and explicit_avg_cost > 0:
                explicit_cost = round(explicit_shares * explicit_avg_cost, 2)
                share_delta = round(explicit_shares - total_shares, 4)
                cost_delta = round(explicit_cost - total_cost, 2)
                share_threshold = max(0.01, max(explicit_shares, total_shares) * 0.001)
                cost_threshold = max(1.0, max(explicit_cost, total_cost) * 0.005)
                config_pending = float(getattr(holding_config, "pending_amount", 0) or 0) if holding_config else 0.0
                pending_delta = round(config_pending - pending_amount, 2)
                if (
                    abs(share_delta) > share_threshold
                    or abs(cost_delta) > cost_threshold
                    or abs(pending_delta) > 1.0
                ):
                    ledger_warning = {
                        "code": code,
                        "name": fund.get("name", code),
                        "computed_shares": total_shares,
                        "configured_shares": explicit_shares,
                        "share_delta": share_delta,
                        "computed_cost": total_cost,
                        "configured_cost": explicit_cost,
                        "cost_delta": cost_delta,
                        "computed_pending_amount": pending_amount,
                        "configured_pending_amount": config_pending,
                        "pending_delta": pending_delta,
                        "purchase_amount": purchase_amount,
                        "reason": "配置中的 shares/avg_cost/pending_amount 只用于诊断；报告口径以交易流水计算结果为准",
                        "is_dca_pending": pending_amount > 0,
                    }
                    ledger_warnings.append(ledger_warning)

            week_start_nav = _match_nav_on_or_before(nav_map, today - timedelta(days=7))
            week_start_value = round(total_shares * week_start_nav, 2) if week_start_nav else None
            week_profit = round(display_value - week_start_value, 2) if week_start_value else None
            week_return_pct = round(week_profit / week_start_value * 100, 2) if week_start_value else None

            day_profit = None
            day_return_pct = None
            if nav_map and last_nav_date:
                previous_nav_dates = [d for d in nav_map.keys() if d < last_nav_date]
                if previous_nav_dates:
                    previous_nav = nav_map[max(previous_nav_dates)]
                    previous_value = round(total_shares * previous_nav, 2)
                    day_profit = round(display_value - previous_value, 2)
                    day_return_pct = round(day_profit / previous_value * 100, 2) if previous_value else None

            dca_records = []
            if dca_strategy:
                dca_records = _simulate_dca_for_report(dca_strategy, nav_map, today)

            if result.get("has_calibration_error"):
                for rej in result.get("calibrations_rejected", []):
                    print(f"  [CALIB WARN] {code}: {rej['reason']} "
                          f"(计算={rej['computed_shares']}, 真实={rej['actual_shares']}, "
                          f"偏差={rej['delta_pct']}%)")
                    calibration_warnings.append({
                        "code": code, "name": fund.get("name", code),
                        "rejected": rej,
                    })

            analysis = {
                "fund_code": code,
                "fund_name": fund.get("name", code),
                "total_cost": total_cost,
                "total_shares": total_shares,
                "simulated_shares": result["total_shares"],
                "current_nav": result["current_nav"],
                "nav_date": max(nav_map.keys()).isoformat() if nav_map else None,
                "current_value": display_value,
                "profit": display_profit,
                "return_pct": display_return_pct,
                "portfolio_pnl": result["portfolio_pnl"],
                "annual_return": round(result["xirr"] * 100, 1),
                "avg_cost": avg_cost,
                "pending_amount": round(pending_amount, 2),
                "purchase_amount": purchase_amount,
                "ledger_warning": ledger_warning,
                "week_start_value": week_start_value,
                "week_profit": week_profit,
                "week_return_pct": week_return_pct,
                "day_profit": day_profit,
                "day_return_pct": day_return_pct,
                "dca_records": dca_records,
                "dca_enabled": bool(dca_strategy),
                "dca_avg_cost": 0.0,
                "nav_trend": [],
                "value_trend": [],
                "engine_events": result["events_detail"],
                "calibrations_applied": result["calibrations_applied"],
                "calibrations_rejected": result.get("calibrations_rejected", []),
                "xirr": result["xirr"],
                "settle_delay": settle_delay,
                "fund_type": getattr(holding_config, "type", ""),
                "days_held": (today - min(p["date"] for p in purchases if p.get("date"))).days if purchases else 0,
            }
            analyses.append(analysis)

        except Exception as e:
            print(f"  [WARN] {code} 持仓分析失败: {e}")

    result = portfolio_summary(analyses)
    if calibration_warnings:
        result["calibration_warnings"] = calibration_warnings
    if ledger_warnings:
        result["ledger_warnings"] = ledger_warnings
    return result


def _match_nav_on_or_before(nav_map: dict, target: date):
    if not nav_map:
        return None
    candidates = [d for d in nav_map.keys() if d <= target]
    if not candidates:
        return None
    return nav_map[max(candidates)]


def _build_workflow_context(config, holdings_data, news_data=None, portfolio_risk_matrix=None):
    """Build report sections that depend on trading-day workflow."""
    from src.engine.calendar import is_trade_day
    from src.engine.calculator import _settlement_date
    from src.engine.events import resolve_nav_date, _effective_trade_date

    run_date = _shared_today()
    report_date = effective_report_date()
    is_run_trade_day = is_trade_day(run_date)
    is_report_current = report_date == run_date
    is_trade_report = is_run_trade_day and is_report_current
    by_fund = (holdings_data or {}).get("by_fund", {})

    dca_rows = []
    for holding in config.holdings:
        if not holding.dca or not holding.dca.enabled:
            continue

        scheduled_date = holding.dca.start_date
        status = "今日执行" if scheduled_date == run_date and is_trade_report else "等待下次"
        if scheduled_date and scheduled_date < run_date:
            status = "待滚动/待确认"
        trade_date = None
        nav_date = None
        settle_date = None
        if scheduled_date:
            trade_date = _effective_trade_date(scheduled_date, after_1500=False)
            nav_date = resolve_nav_date(scheduled_date, after_1500=False, settle_delay=holding.settle_delay)
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

    qdii_rows = []
    for fund in (holdings_data or {}).get("funds", []):
        detail = by_fund.get(fund["code"], {})
        if int(detail.get("settle_delay", 1)) < 2:
            continue
        pending_events = [
            e for e in detail.get("engine_events", [])
            if e.get("type") == "BUY" and e.get("status") == "PENDING"
        ]
        qdii_rows.append({
            "code": fund["code"],
            "name": fund["name"],
            "current_nav": detail.get("current_nav", 0),
            "nav_date": detail.get("nav_date", ""),
            "shares": detail.get("total_shares", 0),
            "simulated_shares": detail.get("simulated_shares", 0),
            "pending_amount": detail.get("pending_amount", 0),
            "pending_events": pending_events,
            "settlement_status": "有待确认交易" if pending_events or detail.get("pending_amount", 0) > 0 else "已确认",
        })

    top_news = []
    for item in news_data or []:
        news_list = item.get("news_list", [])
        if news_list:
            top_news.append({
                "code": item.get("fund_code", ""),
                "name": item.get("fund_name", ""),
                "sentiment": item.get("sentiment_mean", 0.5),
                "headline": news_list[0].get("title", ""),
                "date": news_list[0].get("date", ""),
            })

    return {
        "run_date": run_date.isoformat(),
        "report_date": report_date.isoformat(),
        "run_is_trade_day": is_run_trade_day,
        "is_trade_day": is_trade_report,
        "mode": "current_trade_day" if is_trade_report else "prior_settlement",
        "mode_reason": "当前交易日数据已过分界点" if is_trade_report else "使用上一口径日数据",
        "dca_rows": dca_rows,
        "qdii_rows": qdii_rows,
        "top_news": top_news[:8],
        "portfolio_risk_matrix": portfolio_risk_matrix or {},
    }


def _simulate_dca_for_report(dca_strategy: dict, nav_map: dict, today) -> list:
    """为报告生成 DCA 模拟明细（兼容旧格式）。"""
    from src.engine.events import _generate_dca_dates
    from datetime import date
    records = []
    dca_start = dca_strategy.get("start_date")
    if not dca_start:
        return records
    dates = _generate_dca_dates(
        dca_start, today,
        dca_strategy.get("frequency", "weekly"),
        dca_strategy.get("day_of_week"),
    )
    cum_shares = 0.0
    prev_value = 0.0
    period = 0
    FEE = dca_strategy.get("fee_rate", 0.0015)

    for d in dates:
        nav = _match_nav_from_map(nav_map, d)
        if not nav:
            continue
        net = dca_strategy["amount"] / (1 + FEE)
        s = round(net / nav, 4)
        cum_shares += s
        cv = round(cum_shares * nav, 2)
        pr = "N/A"
        if period > 0 and prev_value > 0:
            pr = f"{(cv - prev_value) / prev_value * 100:+.1f}%"
        records.append({
            "date": d, "amount": dca_strategy["amount"],
            "nav": round(nav, 4), "shares": s,
            "cum_shares": round(cum_shares, 4),
            "period_return": pr,
        })
        prev_value = cv
        period += 1
    return records


def _match_nav_from_map(nav_map: dict, target) -> float:
    from datetime import date, timedelta
    d = target
    if hasattr(d, 'date'):
        d = d.date()
    if d in nav_map:
        return nav_map[d]
    for i in range(1, 6):
        nd = d + timedelta(days=i)
        if nd in nav_map:
            return nav_map[nd]
    for i in range(1, 4):
        nd = d - timedelta(days=i)
        if nd in nav_map:
            return nav_map[nd]
    return None


def _run_news_analysis(config, analyzer, agent_news_plan=None):
    """运行新闻分析 —— 持仓驱动定向采集 → 去重 → 蒸馏 → 简报"""
    from src.news.pipeline import run_news_pipeline
    return run_news_pipeline(analyzer, config, agent_news_plan, days=7)


def _planned_news_profile(agent_news_plan, code: str):
    if not agent_news_plan:
        return {}
    funds = agent_news_plan.get("funds") or {}
    return funds.get(code) or funds.get(str(code).zfill(6)) or {}


def _planned_news_keywords(agent_news_plan, code: str):
    profile = _planned_news_profile(agent_news_plan, code)
    keywords = []
    for key in ("keywords", "search_terms", "expanded_keywords"):
        for kw in profile.get(key, []) or []:
            if kw and kw not in keywords:
                keywords.append(str(kw))
    # 防御性拆分：将复合关键词（如 "英伟达 NVDA 财报"）按空格拆为原子词
    split_keywords = []
    for kw in keywords:
        parts = kw.split()
        for part in parts:
            part = part.strip()
            if len(part) >= 2 and part not in split_keywords:
                split_keywords.append(part)
    return split_keywords or None


def _build_nav_summary(nav_returns):
    if not nav_returns:
        return "无净值收益率数据"
    latest = nav_returns[-1]
    recent = [r for _, r in nav_returns[-20:]]
    avg = sum(recent) / len(recent) if recent else 0
    return (
        f"最近净值日 {latest[0]}，日增长率 {latest[1]:+.2f}%；"
        f"近20个可用交易日平均日增长率 {avg:+.2f}%"
    )


def _holding_context_for_news(config, code: str) -> str:
    holding = next((h for h in config.holdings if h.code == code), None)
    if not holding:
        return ""
    return (
        f"类型={getattr(holding.type, 'value', holding.type)}; "
        f"币种={holding.currency}; settle_delay={holding.settle_delay}; "
        f"定投={'启用' if holding.dca and holding.dca.enabled else '未启用'}; "
        f"待确认金额={holding.pending_amount}"
    )


def _run_recommendations(news_data, codes, analyzer, portfolio_risk_matrix=None):
    """运行基金推荐"""
    from src.recommend.engine import (
        extract_hot_sectors, screen_funds, filter_by_correlation,
        rank_recommendations, rank_recommendations_with_portfolio,
        generate_recommendation_reasons,
        build_holding_profiles, compute_inter_recommendation_correlations,
    )

    hot_sectors = extract_hot_sectors(news_data)
    candidates = screen_funds(hot_sectors)
    holding_codes = set(codes)
    holding_profiles = build_holding_profiles(analyzer, holding_codes)
    filtered = filter_by_correlation(candidates, holding_codes, holding_profiles)
    if portfolio_risk_matrix:
        ranked = rank_recommendations_with_portfolio(
            filtered,
            hot_sectors,
            portfolio_risk_matrix,
            top_n=5,
        )
    else:
        ranked = rank_recommendations(filtered, hot_sectors, top_n=5)
    final_recs = generate_recommendation_reasons(ranked)
    from src.news.agent_context import build_recommendation_judgment_context
    rec_context = build_recommendation_judgment_context(final_recs, holding_profiles, hot_sectors)
    for rec in final_recs:
        rec["agent_review_required"] = True
    if final_recs:
        final_recs[0]["agent_recommendation_context"] = rec_context
    inter_corr = compute_inter_recommendation_correlations(final_recs)
    return final_recs, inter_corr


def _save_snapshot(store, scores, stress_tests, correlations, holdings_data=None):
    """保存分析快照到数据库"""
    try:
        score_data = [_score_snapshot_payload(s) for s in scores]

        corr_data = []
        if not correlations.empty:
            codes_list = list(correlations.columns)
            for i, c1 in enumerate(codes_list):
                for c2 in codes_list[i+1:]:
                    r = correlations.loc[c1, c2]
                    corr_data.append({
                        "fund_code_1": c1, "fund_code_2": c2,
                        "pearson_r": round(float(r), 4),
                        "is_warning": abs(r) > 0.85,
                    })

        snapshot_id = store.save_analysis({
            "analysis_date": _shared_now(),
            "market_summary": "请参考 report.md",
            "portfolio_total_value": (holdings_data or {}).get("total_value"),
            "portfolio_total_cost": (holdings_data or {}).get("total_cost"),
            "scores": score_data,
            "stress_tests": _sanitize_stress_tests_for_snapshot(stress_tests),
            "correlations": corr_data,
        })
        print(f"快照已保存: ID={snapshot_id}")
    except Exception as e:
        print(f"[WARN] 快照保存失败: {e}")


def _score_snapshot_payload(s):
    """Build the database-safe score payload used by analysis snapshots."""
    return {
        "fund_code": s["fund_code"],
        "data_completeness": s["data_completeness"],
        "composite_score": s["composite_score"],
        "score_level": s["score_level"],
        "score_confidence": s.get("score_confidence"),
        "macro_score": s["macro_score"],
        "macro_basis": s.get("macro_basis", ""),
        "macro_detail": s.get("macro_detail", {}),
        "meso_score": s.get("meso_score"),
        "meso_basis": s.get("meso_basis", ""),
        "meso_detail": s.get("meso_detail", {}),
        "micro_score": s["micro_score"],
        "micro_basis": s.get("micro_basis", ""),
        "micro_detail": s.get("micro_detail", {}),
        "feature_matrix": s.get("feature_matrix"),
        "factor_matrix": s.get("factor_matrix"),
        "trend_matrix": s.get("trend_matrix"),
        "operation_advice": s.get("operation_advice"),
        "recommendation": s["recommendation"],
        "stop_profit_pct": s["stop_profit_pct"],
        "stop_loss_pct": s["stop_loss_pct"],
        "action_logic": s["action_logic"],
        "key_metrics": f"波动率:{s.get('annual_volatility','N/A')}; 夏普:{s.get('sharpe_1y','N/A')}",
    }


def _sanitize_stress_tests_for_snapshot(stress_tests):
    allowed = {
        "scenario_id",
        "scenario_desc",
        "fund_code",
        "estimated_drawdown_pct",
        "portfolio_drawdown_pct",
        "impact_amount",
    }
    return [
        {k: v for k, v in (item or {}).items() if k in allowed}
        for item in (stress_tests or [])
    ]


def _should_snapshot_after_analyze(args) -> bool:
    return getattr(args, "snapshot_after", True)


def cmd_fetch(args):
    """仅拉取净值数据"""
    from src.config.loader import load_portfolio_config
    from src.data.fetcher import fetch_fund_nav

    config = load_portfolio_config(args.config)
    for holding in config.holdings:
        print(f"拉取 {holding.code} {holding.name}...")
        nav = fetch_fund_nav(holding.code)
        print(f"  获取 {len(nav)} 条净值记录")


def cmd_score(args):
    """仅对已有数据库持仓做评分"""
    from src.db.storage import FundStorage
    from src.analysis.scorer import FundAnalyzer
    from src.analysis.correlation import compute_correlations
    from src.analysis.stress import stress_test
    from src.output.report import generate_report

    store = FundStorage()
    holding_funds = store.list_holding_funds()
    codes = [f["code"] for f in holding_funds]

    analyzer = FundAnalyzer()
    for code in codes:
        analyzer.load_fund(code)

    scores = [analyzer.score_fund(c) for c in codes
              if analyzer.funds[c]["completeness"] != "D"]
    correlations = compute_correlations(analyzer.funds)
    if getattr(args, "stress", False):
        stress_results = stress_test(analyzer.funds)
    else:
        stress_results = []

    report = generate_report(analyzer, scores, correlations, stress_results)
    report_path = args.output or "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存: {report_path}")


def cmd_news(args):
    """新闻采集与分析"""
    from src.config.loader import load_portfolio_config
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate

    config = load_portfolio_config(args.config)
    for holding in config.holdings:
        print(f"\n=== {holding.code} {holding.name} ===")
        news = fetch_fund_news(holding.code, holding.name, days=args.days, fund_type=getattr(holding, "type", ""))
        print(f"获取 {len(news)} 条新闻")

        if news:
            sent = analyze_sentiment(news)
            daily = daily_sentiment_aggregate(sent)
            for d in daily[-3:]:
                print(f"  {d['date']}: 情绪均={d['sentiment_mean']:.3f}, "
                      f"正面率={d['positive_rate']:.0%}, "
                      f"关键词={d['top_keywords'][:3]}")


def cmd_recommend(args):
    """基金推荐"""
    from src.config.loader import load_portfolio_config
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from src.recommend.engine import (
        extract_hot_sectors, screen_funds, rank_recommendations,
        generate_recommendation_reasons, filter_by_correlation,
        infer_style_tags, infer_theme, compute_inter_recommendation_correlations,
    )

    config = load_portfolio_config(args.config)

    all_news_results = []
    for holding in config.holdings:
        news = fetch_fund_news(holding.code, holding.name, days=args.days, fund_type=getattr(holding, "type", ""))
        if news:
            sent = analyze_sentiment(news)
            daily = daily_sentiment_aggregate(sent)
            all_news_results.append({
                "fund_code": holding.code,
                "news_list": sent,
                "daily_aggregates": daily,
            })

    hot_sectors = extract_hot_sectors(all_news_results)
    print(f"热点行业: {hot_sectors}")

    candidates = screen_funds(hot_sectors)
    holding_codes = {h.code for h in config.holdings}
    holding_profiles = [{
        "code": h.code,
        "name": h.name,
        "type": getattr(h.type, "value", str(h.type)),
        "theme": infer_theme(h.name, getattr(h.type, "value", str(h.type))),
        "style_tags": infer_style_tags(h.name, getattr(h.type, "value", str(h.type))),
    } for h in config.holdings]
    filtered = filter_by_correlation(candidates, holding_codes, holding_profiles)
    ranked = rank_recommendations(filtered, hot_sectors, top_n=args.top)
    with_reasons = generate_recommendation_reasons(ranked)

    print(f"\n推荐基金 Top-{len(with_reasons)}:")
    for i, rec in enumerate(with_reasons):
        print(f"  {i+1}. {rec.get('code', '')} {rec.get('name', '')} "
              f"| 得分: {rec.get('score', 0):.3f} | {rec.get('reason', '')}")

    inter_corr = compute_inter_recommendation_correlations(with_reasons)
    if inter_corr.get("warnings"):
        print("\n⚠️ 推荐基金间相关性警告:")
        for w in inter_corr["warnings"]:
            print(f"  {w}")


def cmd_diagnose(args):
    """单基金快速诊断"""
    from src.analysis.scorer import FundAnalyzer

    code = args.code
    analyzer = FundAnalyzer()
    analyzer.load_fund(code)

    if code not in analyzer.funds or analyzer.funds[code]["completeness"] == "D":
        print(f"[ERROR] 无法获取 {code} 的足够数据")
        return

    s = analyzer.score_fund(code)
    print(f"\n{s['fund_name']}（{code}）")
    print(f"数据完整度: {s['data_completeness']}")
    print(f"综合评分: {s['composite_score']}/100（{s['score_level_emoji']}）")
    print(f"宏观: {s['macro_score']}/20 | 中观: {s['meso_score']}/30 | 微观: {s['micro_score']}/50")
    print(f"建议: {s['recommendation']}")
    print("评分来源: 规则初稿；最终判断请由接入 skill 的 agent 结合证据校准")
    print(f"止盈: +{s['stop_profit_pct']}% | 止损: {s['stop_loss_pct']}%")
    print(f"依据: {s['action_logic']}")


def _perform_snapshot(config_path):
    """更新当前持仓 YAML：加入已执行定投、更新下次定投日。"""
    import yaml
    from datetime import date
    from src.config.loader import load_portfolio_config
    from src.config.schema import Purchase
    from src.analysis.holdings import _is_business_day, _next_dca_date

    config = load_portfolio_config(config_path)
    today = dca_effective_date()  # 10:00 前当日定投未执行

    for holding in config.holdings:
        if holding.dca and holding.dca.enabled:
            dca = holding.dca
            start = dca.start_date or today

            current = start
            while current <= today:
                if _is_business_day(current):
                    already_exists = any(
                        p.date == current and p.amount == dca.amount
                        for p in holding.purchases
                    )
                    if not already_exists:
                        holding.purchases.append(
                            Purchase(date=current, amount=dca.amount)
                        )
                current = _next_dca_date(current, dca.frequency.value, dca.day_of_week)

            next_date = current
            dca.start_date = next_date

    raw = config.model_dump(mode="json")

    def fmt_date(d):
        if isinstance(d, str):
            return d
        return d.isoformat()

    for h in raw.get("holdings", []):
        for p in h.get("purchases", []):
            if p.get("date"):
                p["date"] = fmt_date(p["date"])
        dca = h.get("dca")
        if dca and dca.get("start_date"):
            dca["start_date"] = fmt_date(dca["start_date"])

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"持仓已更新: {config_path}")


def cmd_snapshot(args):
    """更新当前持仓 YAML（独立子命令入口）"""
    _perform_snapshot(args.config)


def cmd_ui(args):
    """启动交互式 Streamlit 管理界面"""
    import subprocess
    config_path = args.config or "fund-portfolio.yaml"
    env = os.environ.copy()
    env["FUND_CONFIG"] = os.path.abspath(config_path)
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "app.py"),
        "--server.port", str(args.port),
    ], env=env)


def main():
    parser = argparse.ArgumentParser(description="基金分析 Agent CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="生成示例配置文件")
    p_init.add_argument("-o", "--output", default="fund-portfolio.yaml")

    p_import = sub.add_parser("import", help="从 YAML 导入持仓到数据库")
    p_import.add_argument("-c", "--config", required=True, help="YAML 配置文件路径")

    p_analyze = sub.add_parser("analyze", help="完整分析流程")
    p_analyze.add_argument("-c", "--config", required=True)
    p_analyze.add_argument("-o", "--output", default="report.md")
    p_analyze.add_argument("--recommend", action="store_true", help="启用基金推荐（默认关闭）")
    p_analyze.add_argument("--stress", action="store_true", help="启用情景压力测试（默认关闭）")
    p_analyze.add_argument(
        "--snapshot-after",
        action="store_true",
        default=True,
        help="报告生成后滚动定投记录并更新配置文件",
    )
    p_analyze.add_argument(
        "--no-snapshot-after",
        dest="snapshot_after",
        action="store_false",
        help="报告生成后不滚动 fund-portfolio.yaml",
    )
    p_analyze.add_argument(
        "--news-keyword-cache",
        default=None,
        help="Agent 生成的新闻关键词缓存路径，默认 data/cache/news_keyword_profiles.json",
    )

    p_fetch = sub.add_parser("fetch", help="仅拉取净值数据")
    p_fetch.add_argument("-c", "--config", required=True)

    p_score = sub.add_parser("score", help="仅对数据库现有持仓评分")
    p_score.add_argument("-o", "--output", default="report.md")
    p_score.add_argument("--stress", action="store_true", help="启用情景压力测试（默认关闭）")

    p_news = sub.add_parser("news", help="新闻采集与分析")
    p_news.add_argument("-c", "--config", required=True)
    p_news.add_argument("--days", type=int, default=7)

    p_rec = sub.add_parser("recommend", help="基金推荐")
    p_rec.add_argument("-c", "--config", required=True)
    p_rec.add_argument("--top", type=int, default=5)
    p_rec.add_argument("--days", type=int, default=7)

    p_diag = sub.add_parser("diagnose", help="单基金诊断")
    p_diag.add_argument("code", help="6位基金代码")

    p_snap = sub.add_parser("snapshot", help="更新持仓 YAML（含定投记录+备份）")
    p_snap.add_argument("-c", "--config", required=True, help="YAML 配置文件路径")

    p_ui = sub.add_parser("ui", help="启动交互式管理界面 (Streamlit)")
    p_ui.add_argument("-c", "--config", default="fund-portfolio.yaml", help="YAML 配置文件路径")
    p_ui.add_argument("-p", "--port", type=int, default=8501, help="端口号 (默认: 8501)")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "news":
        cmd_news(args)
    elif args.command == "recommend":
        cmd_recommend(args)
    elif args.command == "diagnose":
        cmd_diagnose(args)
    elif args.command == "snapshot":
        cmd_snapshot(args)
    elif args.command == "ui":
        cmd_ui(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
