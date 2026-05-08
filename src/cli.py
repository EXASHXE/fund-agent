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
from datetime import date, datetime

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


def cmd_analyze(args):
    """完整分析流程：快照更新 → 导入 → 采集 → 分析 → 报告"""
    from src.config.loader import load_portfolio_config, import_to_database
    from src.analysis.scorer import FundAnalyzer
    from src.analysis.correlation import compute_correlations
    from src.analysis.stress import stress_test
    from src.analysis.holdings import analyze_holding, portfolio_summary
    from src.output.report import generate_report
    from src.db.storage import FundStorage
    from src.db.database import get_session, get_holdings, get_nav_history

    _perform_snapshot(args.config)
    config = load_portfolio_config(args.config)
    import_to_database(config)

    store = FundStorage()
    holding_funds = store.list_holding_funds()
    if not holding_funds:
        print("[ERROR] 无持仓数据")
        return

    codes = [f["code"] for f in holding_funds]
    print(f"\n持仓基金 {len(codes)} 只: {codes}")

    print("\n[Layer 1] 数据采集...")
    analyzer = FundAnalyzer()
    for code in codes:
        try:
            analyzer.load_fund(code)
        except Exception as e:
            print(f"  [ERROR] {code}: {e}")

    print("\n[Layer 2] 分析打分...")
    scores = []
    unscores = []
    for code in codes:
        if code in analyzer.funds:
            fund = analyzer.funds[code]
            if fund["completeness"] != "D":
                s = analyzer.score_fund(code)
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
    stress_results = stress_test(analyzer.funds)

    # 持仓分析
    holdings_data = _compute_holdings(store, config, codes, analyzer)

    # 新闻分析
    news_data = []
    if not args.skip_news:
        print("\n[新闻] 采集与分析...")
        news_data = _run_news_analysis(config, analyzer)

    # 推荐
    recommendations = []
    if not args.skip_recommend:
        print("\n[推荐] 搜索推荐基金...")
        recommendations = _run_recommendations(news_data, codes, analyzer)

    print("\n[Layer 3] 生成报告...")
    report = generate_report(
        analyzer, scores, correlations, stress_results,
        holdings_data=holdings_data,
        news_data=news_data,
        recommendations=recommendations,
        unscores=unscores,
    )

    report_path = args.output or "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存: {report_path}")

    _save_snapshot(store, scores, stress_results, correlations)


def _compute_holdings(store, config, codes, analyzer=None):
    """计算持仓分析数据 — 使用事件驱动引擎（支持 QDII T+2 + 校准 3% 阈值）。

    流程：交易日历 → 事件生成 → 净值匹配(含 settle_delay) → XIRR 计算 → 校准平账。
    """
    from src.engine.events import generate_events
    from src.engine.calculator import compute_fund
    from src.analysis.holdings import portfolio_summary
    from src.db.database import get_session, get_holdings

    session = get_session()
    today = date.today()
    analyses = []
    calibration_warnings = []

    for code in codes:
        try:
            fund = store.get_fund(code)
            if not fund:
                continue

            holdings = get_holdings(session, fund["id"])
            purchases = [{"date": h.buy_date, "amount": h.amount,
                          "nav": h.nav, "after_1500": h.after_1500 if hasattr(h, 'after_1500') else False}
                         for h in holdings]

            holding_config = next((h for h in config.holdings if h.code == code), None)

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

            fee_rate = float(getattr(holding_config, 'fee_rate', None) or 0.0015)
            settle_delay = int(getattr(holding_config, 'settle_delay', None) or 1)

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
                nav_list = get_nav_history(session, fund["id"])
                for n in nav_list:
                    nav_map[n.date] = float(n.nav)
                if nav_map:
                    last_nav_date = max(nav_map.keys())
                    current_nav = nav_map[last_nav_date]

            if last_nav_date and (today - last_nav_date).days > 1:
                from src.analysis.holdings import estimate_current_nav
                est = estimate_current_nav(code, current_nav, last_nav_date, today)
                if est and est > 0 and est != current_nav:
                    nav_map[today] = est
                    current_nav = est

            events = generate_events(purchases, dca_strategy, calibrations, today)

            result = compute_fund(events, nav_map, fee_rate, settle_delay, today)

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
                "total_cost": result["total_cost"],
                "total_shares": result["total_shares"],
                "current_value": result["current_asset"],
                "profit": result["profit"],
                "return_pct": result["return_pct"],
                "annual_return": round(result["xirr"] * 100, 1),
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
            }
            analyses.append(analysis)

        except Exception as e:
            print(f"  [WARN] {code} 持仓分析失败: {e}")

    result = portfolio_summary(analyses)
    if calibration_warnings:
        result["calibration_warnings"] = calibration_warnings
    return result


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
    return None


def _run_news_analysis(config, analyzer):
    """运行新闻分析"""
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from src.news.correlate import news_nav_correlation

    results = []
    for holding in config.holdings:
        code = holding.code
        name = holding.name
        fund_data = analyzer.funds.get(code, {})

        news_list = fetch_fund_news(code, name, days=7)
        if not news_list:
            continue

        news_with_sent = analyze_sentiment(news_list)
        daily_agg = daily_sentiment_aggregate(news_with_sent)

        nav_df = fund_data.get("nav", None)
        nav_returns = []
        if nav_df is not None and not (hasattr(nav_df, 'empty') and nav_df.empty):
            if hasattr(nav_df, 'index'):
                for idx, row in nav_df.iterrows():
                    d = idx.date() if hasattr(idx, 'date') else idx
                    ret = row.get("日增长率", 0)
                    if ret and not (hasattr(ret, '__isnan__') and ret != ret):
                        nav_returns.append((d, float(ret)))

        corr = news_nav_correlation(daily_agg, nav_returns) if nav_returns else {}

        results.append({
            "fund_code": code,
            "fund_name": name,
            "news_count": len(news_list),
            "sentiment_mean": daily_agg[-1]["sentiment_mean"] if daily_agg else 0.5,
            "daily_aggregates": daily_agg,
            "correlation": corr.get(1, (0.0, 1.0))[0],
            "news_list": news_with_sent,
        })

    return results


def _run_recommendations(news_data, codes, analyzer):
    """运行基金推荐"""
    from src.recommend.engine import (
        extract_hot_sectors, screen_funds, filter_by_correlation,
        rank_recommendations, generate_recommendation_reasons
    )

    hot_sectors = extract_hot_sectors(news_data)
    candidates = screen_funds(hot_sectors)
    filtered = filter_by_correlation(candidates, set(codes))
    ranked = rank_recommendations(filtered, hot_sectors, top_n=5)
    return generate_recommendation_reasons(ranked)


def _save_snapshot(store, scores, stress_tests, correlations):
    """保存分析快照到数据库"""
    try:
        score_data = []
        for s in scores:
            score_data.append({
                "fund_code": s["fund_code"],
                "data_completeness": s["data_completeness"],
                "composite_score": s["composite_score"],
                "score_level": s["score_level"],
                "macro_score": s["macro_score"], "macro_basis": s["macro_basis"],
                "macro_detail": s["macro_detail"],
                "meso_score": s["meso_score"],
                "meso_basis": s.get("meso_basis", ""),
                "meso_detail": s["meso_detail"],
                "micro_score": s["micro_score"], "micro_basis": s["micro_basis"],
                "micro_detail": s["micro_detail"],
                "recommendation": s["recommendation"],
                "stop_profit_pct": s["stop_profit_pct"],
                "stop_loss_pct": s["stop_loss_pct"],
                "action_logic": s["action_logic"],
                "key_metrics": f"波动率:{s.get('annual_volatility','N/A')}; 夏普:{s.get('sharpe_1y','N/A')}",
            })

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
            "analysis_date": datetime.now(),
            "market_summary": "请参考 report.md",
            "scores": score_data,
            "stress_tests": stress_tests,
            "correlations": corr_data,
        })
        print(f"快照已保存: ID={snapshot_id}")
    except Exception as e:
        print(f"[WARN] 快照保存失败: {e}")


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
    stress_results = stress_test(analyzer.funds)

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
        news = fetch_fund_news(holding.code, holding.name, days=args.days)
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
    )

    config = load_portfolio_config(args.config)

    all_news_results = []
    for holding in config.holdings:
        news = fetch_fund_news(holding.code, holding.name, days=args.days)
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
    filtered = filter_by_correlation(candidates, holding_codes)
    ranked = rank_recommendations(filtered, hot_sectors, top_n=args.top)
    with_reasons = generate_recommendation_reasons(ranked)

    print(f"\n推荐基金 Top-{len(with_reasons)}:")
    for i, rec in enumerate(with_reasons):
        print(f"  {i+1}. {rec.get('code', '')} {rec.get('name', '')} "
              f"| 得分: {rec.get('score', 0):.3f} | {rec.get('reason', '')}")


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
    print(f"止盈: +{s['stop_profit_pct']}% | 止损: {s['stop_loss_pct']}%")
    print(f"依据: {s['action_logic']}")


def _perform_snapshot(config_path):
    """更新当前持仓 YAML：加入已执行定投、更新下次定投日，同时保存备份。"""
    import yaml
    import shutil
    from datetime import date
    from src.config.loader import load_portfolio_config
    from src.config.schema import Purchase
    from src.analysis.holdings import _is_business_day, _next_dca_date

    config = load_portfolio_config(config_path)
    today = date.today()

    backup_path = f"{config_path}.{today.isoformat()}.bak"
    shutil.copy2(config_path, backup_path)
    _cleanup_bak_files(config_path, keep=1)
    print(f"已备份: {backup_path}")

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


def _cleanup_bak_files(config_path: str, keep: int = 1):
    """保留最近 N 个 .bak 备份文件，删除其余（按文件名日期排序）。"""
    import glob as _glob
    import re as _re
    pattern = f"{config_path}.*.bak"
    files = _glob.glob(pattern)
    files_with_date = []
    for f in files:
        m = _re.search(r'(\d{4}-\d{2}-\d{2})\.bak$', f)
        if m:
            files_with_date.append((m.group(1), f))
    files_with_date.sort(key=lambda x: x[0], reverse=True)
    for _, old in files_with_date[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass


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
    p_analyze.add_argument("--skip-news", action="store_true")
    p_analyze.add_argument("--skip-recommend", action="store_true")

    p_fetch = sub.add_parser("fetch", help="仅拉取净值数据")
    p_fetch.add_argument("-c", "--config", required=True)

    p_score = sub.add_parser("score", help="仅对数据库现有持仓评分")
    p_score.add_argument("-o", "--output", default="report.md")

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
