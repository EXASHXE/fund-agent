"""Core execution workflows for fund-agent commands."""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from src.config.shared import effective_report_date, today as shared_today
from src.services.news_service import (
    news_context_by_code,
    write_keyword_request_and_exit,
)
from src.services.portfolio_service import build_workflow_context, compute_holdings

from src.services.report_service import load_decisions_for_run, render_analysis_report
from src.services.scoring_service import attach_decision_evidence, attach_score_trends
from src.services.snapshot_service import (
    perform_snapshot,
    save_snapshot,
    should_snapshot_after_analyze,
)


KeywordCallback = Callable[[list[str], list[dict]], dict | None]


def run_analyze(args, keyword_callback: KeywordCallback | None = None):
    """Run the full analyze workflow from data collection to report output."""
    from src.analysis.correlation import compute_correlations
    from src.analysis.portfolio_risk import build_portfolio_risk_matrix
    from src.analysis.scorer import FundAnalyzer
    from src.analysis.stress import stress_test
    from src.config.loader import import_to_database, load_portfolio_config
    from src.db.storage import FundStorage

    config = load_portfolio_config(args.config)
    import_to_database(config)

    store = FundStorage()
    if not config.holdings:
        print("[ERROR] 无持仓数据")
        return

    codes = [holding.code for holding in config.holdings]
    report_date = effective_report_date()
    print(f"\n持仓基金 {len(codes)} 只: {codes}")
    print(f"报告口径日: {report_date.isoformat()}")

    print("\n[Layer 1] 数据采集...")
    print("Agent 模式: 脚本生成数据证据包；最终评分/新闻/压力测试/推荐由接入 skill 的模型判断")

    analyzer = FundAnalyzer()
    for code in codes:
        try:
            analyzer.load_fund(code)
        except Exception as exc:
            print(f"  [ERROR] {code}: {exc}")

    news_keyword_plan = _resolve_news_keyword_plan(args, codes, analyzer, keyword_callback)
    if not news_keyword_plan:
        write_keyword_request_and_exit(config, codes, analyzer, args.output or "report.md")
        return

    print("\n[Layer 2] 新闻采集与分析...")
    from src.news.pipeline import run_news_pipeline
    news_data = run_news_pipeline(
        analyzer,
        config,
        agent_news_plan=news_keyword_plan,
        days=7,
        report_date=report_date,
    )
    news_contexts = news_context_by_code(news_data)

    print("\n[Layer 3] 分析打分...")
    scores, unscores = _score_funds(codes, analyzer, news_contexts)

    correlations = compute_correlations(analyzer.funds)
    if getattr(args, "stress", False):
        stress_results = stress_test(analyzer.funds)
        print(f"\n  压力测试: {len(stress_results)} 条风险线索")
    else:
        stress_results = []
        print("\n  [默认跳过] 压力测试（--stress 启用）")

    attach_score_trends(store, scores)

    holdings_data = compute_holdings(store, config, codes, analyzer)
    attach_decision_evidence(scores, news_contexts, holdings_data)
    portfolio_risk_matrix = build_portfolio_risk_matrix(holdings_data, scores, correlations)
    workflow_context = build_workflow_context(config, holdings_data, news_data=news_data)
    if isinstance(workflow_context, dict):
        workflow_context["portfolio_risk_matrix"] = portfolio_risk_matrix

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

    agent_decisions = load_decisions_for_run(
        getattr(args, "agent_decisions", None),
        report_date,
        scores=scores,
        news_data=news_data,
        recommendation_candidates=recommendations,
    )
    report_path = args.output or "report.md"
    print("\n[Layer 4] 构建报告证据...")
    print("[Layer 5] 生成最终报告..." if agent_decisions else "[Layer 5] 生成待 Agent 研判的证据稿...")
    report_result = render_analysis_report(
        output_path=report_path,
        report_date=report_date,
        analyzer=analyzer,
        scores=scores,
        correlations=correlations,
        stress_results=stress_results,
        holdings_data=holdings_data,
        news_data=news_data,
        recommendations=recommendations,
        recommendation_status=recommendation_status,
        unscores=unscores,
        workflow_context=workflow_context,
        inter_recommendation_correlations=inter_recommendation_correlations,
        agent_decisions=agent_decisions,
        holding_count=len(config.holdings),
    )
    print(f"报告证据已保存: {report_result.evidence_path}")
    print(f"报告已保存: {report_path}")

    save_snapshot(store, scores, stress_results, correlations, holdings_data=holdings_data)
    if should_snapshot_after_analyze(args):
        perform_snapshot(args.config)


def _resolve_news_keyword_plan(args, codes: list[str], analyzer, keyword_callback: KeywordCallback | None):
    from src.news.keyword_cache import (
        CACHE_VERSION,
        default_keyword_cache_path,
        load_valid_keyword_cache,
    )

    keyword_cache_path = (
        getattr(args, "news_keyword_cache", None)
        or default_keyword_cache_path()
    )
    news_keyword_plan = load_valid_keyword_cache(keyword_cache_path, codes, today=shared_today())
    if news_keyword_plan:
        return news_keyword_plan

    fund_profiles = []
    for code in codes:
        basic = analyzer.funds.get(code, {}).get("basic", {})
        fund_profiles.append({
            "code": code,
            "name": basic.get("name", code),
            "type": basic.get("fund_type", ""),
        })
    agent_keywords = keyword_callback(codes, fund_profiles) if keyword_callback else None
    if agent_keywords:
        return {
            "cache_version": CACHE_VERSION,
            "holding_codes": sorted(codes),
            "generated_at": shared_today().isoformat(),
            "funds": {
                code: {"keywords": agent_keywords.get(code, [])}
                for code in codes
            },
        }

    if not getattr(args, "fallback_keywords", False):
        return None

    print("\n[CLI] 未找到有效的新闻关键词缓存且无 Agent，启用 --fallback-keywords 模式自动生成在途关键词进行分析...")
    from src.news.news_fetcher import _fallback_fund_keywords, extract_holding_keywords

    fallback_plan_funds = {}
    for code in codes:
        basic = analyzer.funds.get(code, {}).get("basic", {})
        name = basic.get("name", code)
        fund_type = basic.get("fund_type", "")
        _, stock_keywords = extract_holding_keywords(code, limit=10)
        theme_keywords = _fallback_fund_keywords(name, fund_type)
        keywords = list(dict.fromkeys(stock_keywords + theme_keywords))
        fallback_plan_funds[code] = {"keywords": keywords}
        print(f"  {code} ({name}) 自动提取关键词: {keywords}")

    news_keyword_plan = {
        "cache_version": CACHE_VERSION,
        "holding_codes": sorted(codes),
        "generated_at": shared_today().isoformat(),
        "funds": fallback_plan_funds,
    }
    try:
        os.makedirs(os.path.dirname(os.path.abspath(keyword_cache_path)), exist_ok=True)
        with open(keyword_cache_path, "w", encoding="utf-8") as handle:
            json.dump(news_keyword_plan, handle, ensure_ascii=False, indent=2)
        print(f"[CLI] 已将自动生成的关键词缓存保存至: {keyword_cache_path}")
    except Exception as exc:
        print(f"[WARNING] 保存关键词缓存失败: {exc}")
    return news_keyword_plan


def _score_funds(codes: list[str], analyzer, news_contexts):
    scores = []
    unscores = []
    for code in codes:
        if code in analyzer.funds:
            fund = analyzer.funds[code]
            if fund["completeness"] != "D":
                score = analyzer.score_fund(code, news_context=news_contexts.get(code))
                scores.append(score)
                print(f"  {code}: {score['composite_score']}/100 ({score['score_level_emoji']})")
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
    return scores, unscores


def _run_recommendations(news_data, codes, analyzer, portfolio_risk_matrix=None):
    from src.news.agent_context import build_recommendation_judgment_context
    from src.recommend.engine import (
        build_holding_profiles,
        compute_inter_recommendation_correlations,
        extract_hot_sectors,
        filter_by_correlation,
        generate_recommendation_reasons,
        rank_recommendations,
        rank_recommendations_with_portfolio,
        screen_funds,
    )

    hot_sectors = extract_hot_sectors(news_data)
    candidates = screen_funds(hot_sectors)
    holding_codes = set(codes)
    holding_profiles = build_holding_profiles(analyzer, holding_codes)
    filtered = filter_by_correlation(candidates, holding_codes, holding_profiles)
    if portfolio_risk_matrix:
        ranked = rank_recommendations_with_portfolio(
            filtered, hot_sectors, portfolio_risk_matrix, top_n=5,
        )
    else:
        ranked = rank_recommendations(filtered, hot_sectors, top_n=5)
    final_recs = generate_recommendation_reasons(ranked)
    rec_context = build_recommendation_judgment_context(final_recs, holding_profiles, hot_sectors)
    for rec in final_recs:
        rec["agent_review_required"] = True
    if final_recs:
        final_recs[0]["agent_recommendation_context"] = rec_context
    inter_corr = compute_inter_recommendation_correlations(final_recs)
    return final_recs, inter_corr
