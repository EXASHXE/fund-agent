"""Command handlers used by the CLI router."""

from __future__ import annotations

import os
import subprocess
import sys

from src.core.workflow import run_analyze
from src.services.snapshot_service import perform_snapshot


def cmd_init(args):
    """生成示例 YAML 配置文件"""
    from src.config.loader import generate_sample_yaml

    output = args.output or "fund-portfolio.yaml"
    generate_sample_yaml(output)


def cmd_import(args):
    """导入持仓配置到数据库"""
    from src.config.loader import import_to_database, load_portfolio_config

    config = load_portfolio_config(args.config)
    print(f"加载配置: {len(config.holdings)} 只基金, {len(config.watchlist)} 只自选")
    import_to_database(config)
    print("导入完成。")


def cmd_analyze(args, keyword_callback=None):
    """Run the core analyze workflow."""
    return run_analyze(args, keyword_callback=keyword_callback)


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
    """仅对已有数据库持仓评分并生成证据稿。"""
    from src.analysis.correlation import compute_correlations
    from src.analysis.scorer import FundAnalyzer
    from src.analysis.stress import stress_test
    from src.db.storage import FundStorage
    from src.output.report import generate_report

    store = FundStorage()
    holding_funds = store.list_holding_funds()
    codes = [fund["code"] for fund in holding_funds]

    analyzer = FundAnalyzer()
    for code in codes:
        analyzer.load_fund(code)

    scores = [
        analyzer.score_fund(code)
        for code in codes
        if analyzer.funds[code]["completeness"] != "D"
    ]
    correlations = compute_correlations(analyzer.funds)
    stress_results = stress_test(analyzer.funds) if getattr(args, "stress", False) else []

    report = generate_report(analyzer, scores, correlations, stress_results)
    report_path = args.output or "report.md"
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(f"报告已保存: {report_path}")


def cmd_news(args):
    """新闻采集与分析"""
    from src.config.loader import load_portfolio_config
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate

    config = load_portfolio_config(args.config)
    for holding in config.holdings:
        print(f"\n=== {holding.code} {holding.name} ===")
        news = fetch_fund_news(
            holding.code,
            holding.name,
            days=args.days,
            fund_type=getattr(holding, "type", ""),
        )
        print(f"获取 {len(news)} 条新闻")

        if news:
            sent = analyze_sentiment(news)
            daily = daily_sentiment_aggregate(sent)
            for item in daily[-3:]:
                print(
                    f"  {item['date']}: 情绪均={item['sentiment_mean']:.3f}, "
                    f"正面率={item['positive_rate']:.0%}, "
                    f"关键词={item['top_keywords'][:3]}"
                )


def cmd_recommend(args):
    """基金推荐"""
    from src.config.loader import load_portfolio_config
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from src.recommend.engine import (
        compute_inter_recommendation_correlations,
        extract_hot_sectors,
        filter_by_correlation,
        generate_recommendation_reasons,
        infer_style_tags,
        infer_theme,
        rank_recommendations,
        screen_funds,
    )

    config = load_portfolio_config(args.config)

    all_news_results = []
    for holding in config.holdings:
        news = fetch_fund_news(
            holding.code,
            holding.name,
            days=args.days,
            fund_type=getattr(holding, "type", ""),
        )
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
    holding_codes = {holding.code for holding in config.holdings}
    holding_profiles = [
        {
            "code": holding.code,
            "name": holding.name,
            "type": getattr(holding.type, "value", str(holding.type)),
            "theme": infer_theme(holding.name, getattr(holding.type, "value", str(holding.type))),
            "style_tags": infer_style_tags(holding.name, getattr(holding.type, "value", str(holding.type))),
        }
        for holding in config.holdings
    ]
    filtered = filter_by_correlation(candidates, holding_codes, holding_profiles)
    ranked = rank_recommendations(filtered, hot_sectors, top_n=args.top)
    with_reasons = generate_recommendation_reasons(ranked)

    print(f"\n推荐基金 Top-{len(with_reasons)}:")
    for index, rec in enumerate(with_reasons):
        print(
            f"  {index + 1}. {rec.get('code', '')} {rec.get('name', '')} "
            f"| 得分: {rec.get('score', 0):.3f} | {rec.get('reason', '')}"
        )

    inter_corr = compute_inter_recommendation_correlations(with_reasons)
    if inter_corr.get("warnings"):
        print("\n⚠️ 推荐基金间相关性警告:")
        for warning in inter_corr["warnings"]:
            print(f"  {warning}")


def cmd_diagnose(args):
    """单基金快速诊断"""
    from src.analysis.scorer import FundAnalyzer
    import pandas as pd

    code = args.code
    analyzer = FundAnalyzer()
    analyzer.load_fund(code)

    if code not in analyzer.funds or analyzer.funds[code]["completeness"] == "D":
        print(f"[ERROR] 无法获取 {code} 的足够数据")
        return

    score = analyzer.score_fund(code)
    nav_df = analyzer.funds[code].get("nav")
    latest_nav = None
    latest_nav_date = None
    latest_return = None
    if isinstance(nav_df, pd.DataFrame) and not nav_df.empty:
        nav_df_sorted = nav_df.sort_index()
        latest_date = nav_df_sorted.index[-1]
        latest_nav_date = latest_date.date() if hasattr(latest_date, "date") else latest_date
        latest_nav = float(nav_df_sorted.loc[latest_date, "单位净值"])
        if "日增长率" in nav_df_sorted.columns:
            latest_return = float(nav_df_sorted.loc[latest_date, "日增长率"])

    _print_diagnosis(code, score, latest_nav, latest_nav_date, latest_return)


def _print_diagnosis(code, score, latest_nav, latest_nav_date, latest_return):
    factor_names = {
        "fund_type_cycle_fit": "基金类型与周期匹配",
        "sector_position": "行业估值与仓位水位",
        "hhi_index": "持仓个股集中度",
        "news_catalyst": "新闻舆情催化",
        "sortino_ratio": "索提诺下行风险比",
        "sharpe_1y": "夏普超额回报比",
        "max_drawdown_3y_pct": "最大回撤控制能力",
        "annual_volatility": "年化波动率适应度",
        "jensen_alpha": "詹森超额收益 Alpha",
        "information_ratio": "基金经理超额能力 IR",
        "beta": "系统贝塔系数 Beta",
    }

    def format_value(key, value):
        if value is None or value == "":
            return "N/A"
        try:
            number = float(value)
        except (ValueError, TypeError):
            return str(value)
        if key in ("max_drawdown_3y_pct", "annual_volatility"):
            if key == "max_drawdown_3y_pct" and number > 0:
                return f"-{number:.2f}%"
            return f"{number:.2f}%"
        if key in ("jensen_alpha", "beta", "sortino_ratio", "sharpe_1y", "information_ratio"):
            return f"{number:.4f}" if key == "jensen_alpha" else f"{number:.2f}"
        if key == "hhi_index":
            return f"{number:.4f}"
        return str(value)

    print("=" * 80)
    print("                    公募基金量化分析与深度诊断报告")
    print("=" * 80)
    print(" 【基金基本信息】")
    print(f"   - 基金名称: {score['fund_name']}")
    print(f"   - 基金代码: {code}")
    print(f"   - 基金类型: {score.get('fund_type', 'N/A')} | 基金经理: {score.get('manager', 'N/A')}")
    print(f"   - 数据完整度: {score['data_completeness']}  | 诊断置信度: {int(score.get('score_confidence', 0.5) * 100)}%")
    print()
    print(" 【最新业绩表现】")
    nav_str = f"{latest_nav:.4f}" if latest_nav is not None else "N/A"
    date_str = latest_nav_date.isoformat() if latest_nav_date else "N/A"
    return_str = f"{latest_return:+.2f}%" if latest_return is not None else "N/A"
    print(f"   - 最新单位净值: {nav_str} ({date_str}) | 当日涨跌幅: {return_str}")
    print(f"   - 历史最大回撤 (3年): {format_value('max_drawdown_3y_pct', score.get('max_drawdown_3y'))}")
    print(f"   - 年化波动率 (1年): {format_value('annual_volatility', score.get('annual_volatility'))}")

    features = score.get("feature_matrix", {})
    print(f"   - 夏普比率 (1年): {format_value('sharpe_1y', features.get('sharpe_1y'))} | 索提诺比率: {format_value('sortino_ratio', features.get('sortino_ratio'))}")
    print(f"   - 詹森 Alpha: {format_value('jensen_alpha', features.get('jensen_alpha'))} | 系统 Beta: {format_value('beta', features.get('beta'))} | 持仓集中度(HHI): {format_value('hhi_index', features.get('hhi_index'))}")
    print()
    print("=" * 80)
    print(f" 基金综合评分: {score['composite_score']} / 100  （{score['score_level_emoji']} {score['score_tendency']}）")
    print("=" * 80)
    print(f" 评分建议: {score['recommendation']}")
    print(f" 止盈触发线: +{score['stop_profit_pct']:.2f}% | 止损保护线: {score['stop_loss_pct']:.2f}%")
    print(f" 宏观得分: {score['macro_score']}/20 | 中观得分: {score.get('meso_score') or 0}/30 | 微观得分: {score['micro_score']}/50")
    print(f" 评分依据: {score['action_logic']}")
    print("-" * 80)
    print(" 评分性质: 规则种子分；最终评定请由接入 skill 的 agent 结合事件研判校准。")
    print()

    print(" 【因子打分拆解 (定量因子矩阵)】")
    factors = score.get("factor_matrix", {})
    _print_factor_block("├─", "宏观", float(score["macro_score"]), 20.0, factors.get("macro", []), factor_names)
    _print_factor_block("├─", "中观", float(score.get("meso_score") or 0), 30.0, factors.get("meso", []), factor_names)
    _print_factor_block("└─", "微观", float(score["micro_score"]), 50.0, factors.get("micro", []), factor_names)
    print("=" * 80)


def _print_factor_block(prefix, label, score, max_score, factors, factor_names):
    print(f" {prefix} {label}维度 (得分: {score:.2f} / {max_score:.2f} 分)")
    child_prefix = " │  " if prefix == "├─" else "    "
    for index, factor in enumerate(factors):
        is_last = index == len(factors) - 1
        branch = "└─" if is_last else "├─"
        name = factor_names.get(factor["name"], factor["name"])
        value = factor.get("value")
        weight = factor.get("weight", 0)
        factor_score = factor.get("score", 0)
        actual_points = weight * factor_score * 100
        max_points = weight * 100
        print(f"{child_prefix}{branch} {name} ({factor['name']})")
        print(
            f"{child_prefix}   [值: {value} | 因子打分: {factor_score * 100:.2f}% "
            f"| 实际得分: {actual_points:.2f} / {max_points:.2f} 分]"
        )


def cmd_snapshot(args):
    """更新当前持仓 YAML（独立子命令入口）"""
    perform_snapshot(args.config)


def cmd_ui(args):
    """启动交互式 Streamlit 管理界面"""
    config_path = args.config or "fund-portfolio.yaml"
    env = os.environ.copy()
    env["FUND_CONFIG"] = os.path.abspath(config_path)
    subprocess.run([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "app.py"),
        "--server.port",
        str(args.port),
    ], env=env)


def command_handlers(keyword_callback=None):
    return {
        "init": cmd_init,
        "import": cmd_import,
        "analyze": lambda args: cmd_analyze(args, keyword_callback=keyword_callback),
        "fetch": cmd_fetch,
        "score": cmd_score,
        "news": cmd_news,
        "recommend": cmd_recommend,
        "diagnose": cmd_diagnose,
        "snapshot": cmd_snapshot,
        "ui": cmd_ui,
    }
