"""Command handlers used by the CLI router."""

from __future__ import annotations

import os
import subprocess
import sys

# Import from src.workflows (thin orchestration layer) instead of
# src.core.workflow directly. The workflows/ module is the architectural
# front door; business logic remains in core/.
from legacy.workflows.analyze import run_analyze
from legacy.services.snapshot_service import perform_snapshot


def cmd_init(args):
    """生成示例 YAML 配置文件"""
    from src.infra.config.loader import generate_sample_yaml

    output = args.output or "fund-portfolio.yaml"
    generate_sample_yaml(output)


def cmd_import(args):
    """导入持仓配置到数据库"""
    from src.infra.config.loader import import_to_database, load_portfolio_config

    config = load_portfolio_config(args.config)
    print(f"加载配置: {len(config.holdings)} 只基金, {len(config.watchlist)} 只自选")
    import_to_database(config)
    print("导入完成。")


def cmd_analyze(args):
    """Run the core analyze workflow."""
    return run_analyze(args)


def cmd_fetch(args):
    """仅拉取净值数据"""
    from src.infra.config.loader import load_portfolio_config
    from src.infra.data.fetcher import fetch_fund_nav

    config = load_portfolio_config(args.config)
    for holding in config.holdings:
        print(f"拉取 {holding.code} {holding.name}...")
        nav = fetch_fund_nav(holding.code)
        print(f"  获取 {len(nav)} 条净值记录")


def cmd_news(args):
    """新闻采集与展示"""
    from src.infra.config.loader import load_portfolio_config
    from legacy.news.news_fetcher import fetch_fund_news

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
            for item in news[:5]:
                title = item.get("title", "")
                date = item.get("date", "")
                print(f"  [{date}] {title}")


def cmd_recommend(args):
    """基金推荐"""
    from src.infra.config.loader import load_portfolio_config
    from legacy.news.news_fetcher import fetch_fund_news
    from legacy.recommend.engine import (
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
            all_news_results.append({
                "fund_code": holding.code,
                "news_list": news,
                "daily_aggregates": [],
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


def command_handlers():
    return {
        "init": cmd_init,
        "import": cmd_import,
        "analyze": cmd_analyze,
        "fetch": cmd_fetch,
        "news": cmd_news,
        "recommend": cmd_recommend,
        "snapshot": cmd_snapshot,
        "ui": cmd_ui,
    }
