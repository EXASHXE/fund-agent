"""Core execution workflows for fund-agent commands."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import networkx as nx
import pandas as pd

from src.config.shared import effective_report_date, today as shared_today
from src.services.news_service import (
    news_context_by_code,
    write_keyword_request_and_exit,
)
from src.services.portfolio_service import compute_holdings
from src.services.workflow_context import build_workflow_context

from src.services.report_service import load_decisions_for_run, render_analysis_report
from src.services.scoring_service import attach_decision_evidence, attach_score_trends
from src.services.snapshot_service import (
    perform_snapshot,
    save_snapshot,
    should_snapshot_after_analyze,
)


KeywordCallback = Callable[[list[str], list[dict]], dict | None]

# ══════════════════════════════════════════════════════════════════════════════
# Adapter helpers for new KG+AI pipeline → old report format
# ══════════════════════════════════════════════════════════════════════════════


def _prepare_fund_data_for_kg(
    code: str, fund_data: dict[str, Any]
) -> dict[str, Any]:
    """Convert analyzer.funds[code] (DataFrame-heavy) to dict for KnowledgeGraphBuilder.

    Args:
        code: Fund code string.
        fund_data: Dict with keys: basic, holdings, sectors (DataFrames), etc.

    Returns:
        Dict with flattened holdings/sectors lists and column-mapped names
        suitable for KnowledgeGraphBuilder.build_from_holdings().
    """
    import pandas as pd

    basic = fund_data.get("basic", {})

    # ── convert holdings DataFrame → list of dicts with normalized keys ──
    holdings_raw = fund_data.get("holdings", pd.DataFrame())
    holdings_list: list[dict] = []
    if isinstance(holdings_raw, pd.DataFrame) and not holdings_raw.empty:
        # Column name mapping: AKShare original → expected by build_from_holdings
        col_map = {
            "股票代码": "stock_code",
            "股票名称": "stock_name",
            "占净值比例": "weight",
            "行业": "industry",
            "行业名称": "industry",
            "所属行业": "sector",
        }
        for _, row in holdings_raw.iterrows():
            h: dict[str, Any] = {}
            for k, v in row.items():
                mapped = col_map.get(str(k), str(k))
                val = v
                # Parse weight (stored as string like "6.23%" in AKShare)
                if mapped == "weight" and isinstance(val, (str, float, int)):
                    try:
                        val = float(str(val).replace("%", "").strip())
                    except (ValueError, TypeError):
                        val = 0.0
                elif mapped in ("industry", "sector"):
                    val = str(val or "")
                elif pd.isna(val):
                    val = "" if mapped != "weight" else 0.0
                h[mapped] = val
            holdings_list.append(h)

    # ── convert sectors DataFrame → list of dicts ──
    sectors_raw = fund_data.get("sectors", pd.DataFrame())
    sectors_list: list[dict] = []
    if isinstance(sectors_raw, pd.DataFrame) and not sectors_raw.empty:
        col_map_sector = {
            "行业名称": "industry",
            "行业代码": "sw_code",
            "占净值比例": "weight",
        }
        for _, row in sectors_raw.iterrows():
            s: dict[str, Any] = {}
            for k, v in row.items():
                mapped = col_map_sector.get(str(k), str(k))
                val = v
                if mapped == "weight" and isinstance(val, (str, float, int)):
                    try:
                        val = float(str(val).replace("%", "").strip())
                    except (ValueError, TypeError):
                        val = 0.0
                elif pd.isna(val):
                    val = "" if mapped != "weight" else 0.0
                s[mapped] = val
            sectors_list.append(s)

    return {
        "code": code,
        "name": basic.get("name", code),
        "fund_type": basic.get("fund_type", ""),
        "style": basic.get("style", ""),
        "holdings": holdings_list,
        "sectors": sectors_list,
    }


def _build_unified_graph(
    analyzer, codes: list[str]
) -> nx.DiGraph:
    """Build a unified Knowledge Graph from all funds in the analyzer.

    Merges per-fund KGs via nx.compose so that shared stock/industry/theme
    nodes are reused across funds.
    """
    from src.kg.graph import KnowledgeGraphBuilder

    kg_builder = KnowledgeGraphBuilder()
    unified = nx.DiGraph()
    for code in codes:
        fund_data_raw = analyzer.funds.get(code, {})
        fund_data = _prepare_fund_data_for_kg(code, fund_data_raw)
        try:
            graph = kg_builder.build_from_holdings(fund_data)
            unified = nx.compose(unified, graph)
        except Exception as exc:
            print(f"  [WARNING] KG build failed for {code}: {exc}")
    return unified


def _adapt_new_news_to_old(
    news_results: dict[str, dict[str, Any]],
    code: str,
    fund_name: str,
) -> dict[str, Any]:
    """Convert new NewsPipeline.run() output to old news_data item format.

    The old format is a list of per-fund dicts consumed by news_context_by_code,
    build_report_evidence, and render_analysis_report.

    Args:
        news_results: Dict mapping fund_code → pipeline result (from NewsPipeline.run).
        code: Fund code for this entry.
        fund_name: Display name of the fund.

    Returns:
        A dict compatible with the old news_data item format.
    """
    result = news_results.get(code) or news_results.get(str(code).zfill(6)) or {}

    scored_news = result.get("scored_news", [])
    raw_news_count = result.get("raw_news_count", len(scored_news))

    # Build old-style news_list from scored news items
    news_list: list[dict] = []
    for sn in scored_news[:20]:  # top 20 for evidence
        news_list.append({
            "title": sn.title or "",
            "content": sn.content or "",
            "date": sn.date or "",
            "source": sn.source or "",
            "sentiment": sn.sentiment_severity,
            "relevance": sn.relevance_score,
        })

    # Compute average sentiment from scored news sentiment_severity
    sentiments = [
        getattr(sn, "sentiment_severity", 0.5)
        for sn in scored_news
        if hasattr(sn, "sentiment_severity")
    ]
    sentiment_mean = round(sum(sentiments) / len(sentiments), 4) if sentiments else 0.5

    # Build minimal daily_aggregates from score news dates
    date_agg: dict[str, dict] = {}
    for sn in scored_news:
        d = getattr(sn, "date", "") or ""
        if d:
            date_agg.setdefault(d, {"date": d, "count": 0, "sentiment_sum": 0.0})
            date_agg[d]["count"] += 1
            date_agg[d]["sentiment_sum"] += getattr(sn, "sentiment_severity", 0.5)
    daily_aggregates = [
        {
            "date": v["date"],
            "news_count": v["count"],
            "sentiment_mean": round(v["sentiment_sum"] / v["count"], 4),
        }
        for v in sorted(date_agg.values(), key=lambda x: x["date"])
    ]

    return {
        "fund_code": code,
        "fund_name": fund_name,
        "news_count": raw_news_count,
        "sentiment_mean": sentiment_mean,
        "daily_aggregates": daily_aggregates,
        "correlation": 0.0,
        "news_list": news_list,
        "post_cutoff_news": [],
        "undated_news": [],
        "catalyst_news": [],
        "brief": {},
        "news_evaluation": {},
        "entity_profile": None,
        "agent_news_context": {},
        "relevance_task": {},
        "status": "ok" if news_list else "empty",
    }


def _adapt_new_score_to_old(
    composite,
    code: str,
    fund_data: dict[str, Any],
    news_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert new ScoreEngine CompositeScore to old score_fund() output format.

    Maps the 5-dimension scoring (quant, fundamental, event, position, timing)
    to the legacy 3-dimension format (macro, meso, micro) for report rendering.

    Args:
        composite: CompositeScore dataclass from ScoreEngine.compute_composite().
        code: Fund code string.
        fund_data: Raw fund_data dict with basic, nav, holdings, etc.
        news_context: Optional news context dict for the fund.

    Returns:
        Dict matching the format produced by analyzer.score_fund().
    """
    from src.analysis.scoring.types import MarketRegime

    basic = fund_data.get("basic", {})
    completeness = fund_data.get("completeness", "D")
    name = basic.get("name", code)

    # ── Map 5 new dimensions → 3 old dimensions ──
    #   macro  ≈ fundamental (fund structure) + regime awareness
    #   meso   ≈ event (industry/event-driven) + position (allocation)
    #   micro  ≈ quant (performance metrics) + timing (entry/exit)
    qs = composite.quant_score
    fs = composite.fundamental_score
    es = composite.event_score
    ps = composite.position_score
    ts = composite.timing_score

    macro_total = int(
        round(fs.score * composite.weights_used.get("fundamental", 0.20)
              * 100 / 0.20)
    )
    meso_total = int(
        round(
            (es.score * composite.weights_used.get("event", 0.15)
             + ps.score * composite.weights_used.get("position", 0.15))
            * 100 / 0.30
        )
    )
    micro_total = int(
        round(
            (qs.score * composite.weights_used.get("quant", 0.40)
             + ts.score * composite.weights_used.get("timing", 0.10))
            * 100 / 0.50
        )
    )

    composite_score = int(round(composite.composite))

    # ── Map level to old emoji/tendency ──
    level_map = {
        "green": ("🟢", "维持或加仓"),
        "yellow": ("🟡", "持有观察，可继续定投"),
        "orange": ("🟠", "减仓或暂停定投"),
        "red": ("🔴", "止盈/止损离场"),
    }
    emoji, tendency = level_map.get(composite.level, ("🟡", "持有观察，可继续定投"))

    # ── Default risk bounds (from fund perf or fallback) ──
    perf_1y = fund_data.get("perf", {}).get("近1年", {})
    vol = round(perf_1y.get("annual_volatility", 20) or 20, 2)
    stop_profit = max(15, min(60, vol * 2.0))
    stop_loss = max(10, min(40, vol * 1.5))

    # ── Build scoring_matrix ──
    scoring_matrix = {
        "quant_baseline": {
            "macro_score": macro_total,
            "meso_score": meso_total,
            "micro_score": micro_total,
            "total_baseline_score": composite_score,
        },
        "agent_overlay": {
            "macro_adjustment": 0,
            "meso_adjustment": 0,
            "micro_adjustment": 0,
            "total_adjustment": 0,
            "overlay_rationale": "",
        },
        "final_score": composite_score,
        "score_tendency": tendency,
    }

    # ── Build feature matrix from detail dicts (best-effort) ──
    qs_detail = getattr(qs, "detail", {}) or {}
    feature_matrix = {
        "hhi_index": qs_detail.get("hhi", 0.0),
        "jensen_alpha": round(float(qs_detail.get("alpha", 0.0)), 4),
        "sortino_ratio": round(float(qs_detail.get("sortino", 0.0)), 4),
        "information_ratio": round(float(qs_detail.get("information_ratio", 0.0)), 4),
        "beta": round(float(qs_detail.get("beta", 1.0)), 4),
        "win_rate_1y": round(float(qs_detail.get("win_rate", 0.0)), 2),
        "calmar_ratio_1y": round(float(qs_detail.get("calmar", 0.0)), 2),
        "max_drawdown_3y_pct": (
            round(float(qs_detail.get("max_drawdown", 0.0)), 2) or None
        ),
        "annual_volatility": round(float(vol), 2),
        "sharpe_1y": round(float(qs_detail.get("sharpe", 0.0)), 2) or None,
    }

    # ── Deduce recommendation ──
    if composite_score >= 75:
        rec_label, rec_logic = "买入 / 逢低加仓", (
            f"综合评分{composite_score}分，处于优质区间。建议维持现有仓位，回调时逢低加仓。"
        )
    elif composite_score >= 60:
        rec_label, rec_logic = "持有 / 继续定投", (
            f"综合评分{composite_score}分，处于中上区间。基金质地尚可，建议继续持有并维持当前定投策略。"
        )
    elif composite_score >= 45:
        rec_label, rec_logic = "持有观察", (
            f"综合评分{composite_score}分，处于中性偏弱区间。建议暂持但暂停新增定投。"
        )
    elif composite_score >= 30:
        rec_label, rec_logic = "减仓 / 暂停定投", (
            f"综合评分{composite_score}分，处于偏弱区间。建议暂停定投，分批减仓。"
        )
    else:
        rec_label, rec_logic = "止损离场", (
            f"综合评分{composite_score}分，处于危险区间。建议尽快止损离场。"
        )

    score = {
        "fund_code": code,
        "fund_name": name,
        "data_completeness": completeness,
        "composite_score": composite_score,
        "score_level": composite.level,
        "score_level_emoji": emoji,
        "score_tendency": tendency,
        "macro_score": macro_total,
        "macro_basis": (
            f"基本面评分 {fs.score:.1f} | 市场状态: {composite.regime.value}"
        ),
        "macro_detail": getattr(fs, "detail", {}),
        "meso_score": meso_total,
        "meso_basis": (
            f"事件评分 {es.score:.1f} + 仓位评分 {ps.score:.1f}"
        ),
        "meso_detail": {
            "event": getattr(es, "detail", {}),
            "position": getattr(ps, "detail", {}),
        },
        "micro_score": micro_total,
        "micro_basis": (
            f"量化评分 {qs.score:.1f} + 择时评分 {ts.score:.1f}"
        ),
        "micro_detail": {
            "quant": qs_detail,
            "timing": getattr(ts, "detail", {}),
        },
        "recommendation": rec_label,
        "action_logic": rec_logic,
        "stop_profit_pct": round(stop_profit, 2),
        "stop_loss_pct": round(-stop_loss, 2),
        "annual_volatility": vol,
        "max_drawdown_3y": None,
        "sharpe_1y": None,
        "fund_type": basic.get("fund_type", ""),
        "manager": basic.get("manager", ""),
        "scoring_matrix": scoring_matrix,
        "feature_matrix": feature_matrix,
        "factor_matrix": {
            "source": "kg_ai_pipeline",
            "regime": composite.regime.value,
            "weights": composite.weights_used,
        },
        "score_confidence": round(
            (qs.confidence + fs.confidence + es.confidence + ps.confidence + ts.confidence) / 5, 2
        ),
        "score_source": "kg_ai_pipeline",
        "agent_review_required": True,
        "agent_score_context": {},
        "trend_evidence": {},
        "risk_constraints": {"requires_agent_decision": True},
    }
    scoring_matrix["final_confidence"] = score["score_confidence"]

    return score


def _score_with_new_engine(
    codes: list[str],
    analyzer,
    graph: nx.DiGraph,
    news_results: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Score all funds using the new ScoreEngine and adapt each to old format.

    Args:
        codes: List of fund codes to score.
        analyzer: FundAnalyzer instance with loaded fund data.
        graph: Unified NetworkX DiGraph from KG.
        news_results: Per-fund news pipeline results.

    Returns:
        Tuple of (scores: list of adapted score dicts, unscores: list of failed dicts).
    """
    from src.analysis.scoring.engine import ScoreEngine

    score_engine = ScoreEngine()
    scores: list[dict[str, Any]] = []
    unscores: list[dict[str, Any]] = []

    for code in codes:
        fund_data = analyzer.funds.get(code)
        if fund_data is None:
            unscores.append({
                "code": code, "name": code, "fund_name": code, "fund_code": code,
                "data_completeness": "D", "error": "数据采集失败",
            })
            continue

        completeness = fund_data.get("completeness", "D")
        if completeness == "D":
            basic = fund_data.get("basic", {})
            unscores.append({
                "code": code, "name": basic.get("name", code),
                "fund_name": basic.get("name", code), "fund_code": code,
                "data_completeness": "D",
                "error": basic.get("error", "核心数据获取失败"),
            })
            continue

        try:
            events = news_results.get(code, {}).get("events", [])
            composite = score_engine.compute_composite(code, fund_data, graph, events)
            adapted = _adapt_new_score_to_old(composite, code, fund_data)
            scores.append(adapted)
            print(
                f"  {code}: {adapted['composite_score']}/100 "
                f"({adapted['score_level_emoji']}) "
                f"[{composite.regime.value}]"
            )
        except Exception as exc:
            print(f"  [ERROR] ScoreEngine failed for {code}: {exc}")
            basic = fund_data.get("basic", {})
            unscores.append({
                "code": code, "name": basic.get("name", code),
                "fund_name": basic.get("name", code), "fund_code": code,
                "data_completeness": completeness,
                "error": f"评分引擎失败: {exc}",
            })

    return scores, unscores


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

    use_agents = getattr(args, "use_agents", False)

    if use_agents:
        # ═══ NEW KG+AI PIPELINE (Phase 2-4) ═══
        print("\n[Layer 2-3] 结合 KG+AI 新流水线...")
        print("  → 构建持仓知识图谱 (KnowledgeGraph)")
        graph = _build_unified_graph(analyzer, codes)
        if graph.number_of_nodes() == 0:
            print("  [ERROR] 知识图谱构建失败，回退到旧流水线")
        else:
            print(f"    图节点: {graph.number_of_nodes()}, 边: {graph.number_of_edges()}")
            # Run new 8-stage news pipeline
            print("  → 运行 8-stage 新闻流水线 (NewsPipeline)")
            try:
                from src.news.news_pipeline import NewsPipeline
                from src.news.finnhub_client import FinnhubNewsClient
                from src.news.tavily_client import TavilySearchClient
                pipeline = NewsPipeline(
                    finnhub_client=FinnhubNewsClient(),
                    tavily_client=TavilySearchClient(),
                )
                news_results = pipeline.run(codes, graph)
                print(f"    完成阶段: {next(iter(news_results.values()), {}).get('stages_completed', [])}")
            except Exception as exc:
                print(f"  [ERROR] NewsPipeline failed: {exc}")
                news_results = {}

            # Score with 5-dimension ScoreEngine
            print("  → 运行 5-dimension 评分引擎 (ScoreEngine)")
            scores, unscores = _score_with_new_engine(codes, analyzer, graph, news_results)

            # Convert new news results to old format for report rendering
            news_data: list[dict[str, Any]] = []
            for code in codes:
                basic = analyzer.funds.get(code, {}).get("basic", {})
                name = basic.get("name", code)
                news_data.append(_adapt_new_news_to_old(news_results, code, name))
            news_contexts = news_context_by_code(news_data)

            # Strategy advice (supplementary, non-fatal on failure)
            try:
                from src.strategy.engine import StrategyEngine
                strategy_engine = StrategyEngine()
                for code in codes:
                    fund_data = analyzer.funds.get(code, {})
                    events = news_results.get(code, {}).get("events", [])
                    advice = strategy_engine.analyze_fund(code, fund_data, graph, events)
                    for s in scores:
                        if s.get("fund_code") == code:
                            s["_strategy_advice"] = {
                                "action": advice.action.value,
                                "confidence": advice.confidence,
                                "risk_level": advice.risk_level,
                                "reasons": advice.reasons,
                                "trigger_events": advice.trigger_events,
                                "position_suggestion": advice.position_suggestion,
                                "time_horizon": advice.time_horizon,
                            }
            except Exception as exc:
                print(f"  [WARNING] StrategyEngine failed: {exc}")

    else:
        # ═══ OLD PIPELINE (unchanged) ═══
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
