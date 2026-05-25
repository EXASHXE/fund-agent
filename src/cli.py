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

try:
    import pandas as pd
    pd.options.mode.string_storage = "python"
except ImportError:
    pass


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
        elif getattr(args, "fallback_keywords", False):
            print("\n[CLI] 未找到有效的新闻关键词缓存且无 Agent，启用 --fallback-keywords 模式自动生成在途关键词进行分析...")
            from src.news.news_fetcher import extract_holding_keywords, _fallback_fund_keywords
            import json
            import os
            
            fallback_plan_funds = {}
            for code in codes:
                fund_data = analyzer.funds.get(code, {})
                basic = fund_data.get("basic", {})
                name = basic.get("name", code)
                fund_type = basic.get("fund_type", "")
                
                # 提取重仓股关键词
                _, stock_kws = extract_holding_keywords(code, limit=10)
                # 提取主题/兜底词
                theme_kws = _fallback_fund_keywords(name, fund_type)
                # 合并去重并保留顺序
                kws = list(dict.fromkeys(stock_kws + theme_kws))
                fallback_plan_funds[code] = {
                    "keywords": kws
                }
                print(f"  {code} ({name}) 自动提取关键词: {kws}")
                
            news_keyword_plan = {
                "cache_version": CACHE_VERSION,
                "holding_codes": sorted(codes),
                "generated_at": _shared_today().isoformat(),
                "funds": fallback_plan_funds,
            }
            # 自动保存到缓存文件，以便后续使用
            try:
                os.makedirs(os.path.dirname(os.path.abspath(keyword_cache_path)), exist_ok=True)
                with open(keyword_cache_path, "w", encoding="utf-8") as f:
                    json.dump(news_keyword_plan, f, ensure_ascii=False, indent=2)
                print(f"[CLI] 已将自动生成的关键词缓存保存至: {keyword_cache_path}")
            except Exception as e:
                print(f"[WARNING] 保存关键词缓存失败: {e}")
        else:
            # 无 Agent：按 SKILL.md 输出关键词请求 JSON 并停止
            _write_keyword_request_and_exit(config, codes, analyzer, args.output or "report.md")
            return  # unreachable, _write_keyword_request_and_exit calls sys.exit

    # 新闻分析前置：新闻催化与情绪作为评分系统的输入证据。
    print("\n[Layer 2] 新闻采集与分析...")
    news_data = _run_news_analysis(
        config, analyzer, agent_news_plan=news_keyword_plan, report_date=report_date
    )
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
    _attach_decision_evidence(scores, news_contexts, holdings_data)
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

    agent_decisions = _load_agent_decisions(
        getattr(args, "agent_decisions", None), report_date, scores=scores, news_data=news_data,
        recommendation_candidates=recommendations,
    )
    evidence = _build_report_evidence(
        report_date, scores, holdings_data, news_data, correlations, stress_results,
        portfolio_risk_matrix, recommendations=recommendations,
        recommendation_status=recommendation_status, workflow_context=workflow_context,
    )
    evidence_path = _write_report_evidence(args.output or "report.md", evidence)
    print(f"\n[Layer 4] 报告证据已保存: {evidence_path}")
    print("[Layer 5] 生成最终报告..." if agent_decisions else "[Layer 5] 生成待 Agent 研判的证据稿...")
    report = generate_report(
        analyzer, scores, correlations, stress_results,
        holdings_data=holdings_data,
        news_data=news_data,
        recommendations=recommendations,
        recommendation_status=recommendation_status,
        unscores=unscores,
        workflow_context=workflow_context,
        inter_recommendation_correlations=inter_recommendation_correlations,
        agent_decisions=agent_decisions,
    )

    # 后置校验：止盈止损校准 + 合规声明追加
    from src.output.validator import post_process_report, validate_final_report
    report = post_process_report(report, scores)
    if agent_decisions:
        validate_final_report(report, report_date.isoformat(), len(config.holdings))

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


def _load_agent_decisions(
    path, report_date, scores=None, news_data=None, recommendation_candidates=None,
):
    """Load and reconcile Agent judgments with this run's evidence contract."""
    if not path:
        return None
    import json

    with open(path, "r", encoding="utf-8") as handle:
        decisions = json.load(handle)
    if decisions.get("schema_version") != "agent_decisions.v2":
        raise ValueError("Agent 决策 schema_version 必须为 agent_decisions.v2")
    decision_date = decisions.get("evidence_report_date")
    expected = report_date.isoformat()
    if decision_date != expected:
        raise ValueError(
            f"Agent 决策口径日 {decision_date or '缺失'} 与报告口径日 {expected} 不一致"
        )
    if not decisions.get("fund_scores"):
        raise ValueError("Agent 决策缺少 fund_scores，不能生成最终报告")
    portfolio = decisions.get("portfolio")
    if not isinstance(portfolio, dict) or not portfolio.get("tldr") or not portfolio.get("stance") or not portfolio.get("daily_analysis"):
        raise ValueError("Agent 决策缺少 portfolio.tldr 或 portfolio.stance 或 portfolio.daily_analysis")
    if not isinstance(decisions.get("recommendations"), list):
        raise ValueError("Agent 决策必须显式提供 recommendations 数组（允许为空）")

    score_lookup = {
        str(item.get("fund_code", "")): item for item in (scores or [])
    }
    missing_funds = sorted(set(score_lookup) - set(decisions["fund_scores"]))
    if missing_funds:
        raise ValueError(f"Agent 决策未覆盖全部评分基金: {', '.join(missing_funds)}")
    for code, baseline in score_lookup.items():
        _validate_fund_decision(code, baseline, decisions["fund_scores"].get(code))

    total_abs_adjust = sum(
        abs(adj)
        for decision in decisions["fund_scores"].values()
        for adj in decision.get("agent_adjustments", {}).values()
        if isinstance(adj, (int, float))
    )
    if total_abs_adjust == 0:
        raise ValueError("所有基金的 Agent 调整评分均未触发（全为 0），不符合投研决策要求。请根据重大新闻、趋势或持仓风险给出至少一个非零调整，并在 rationale 中解释说明。")

    target_sum = sum(
        decision.get("target_weight_pct")
        for decision in decisions["fund_scores"].values()
        if isinstance(decision.get("target_weight_pct"), (int, float))
    )
    if target_sum > 100 + 1e-6:
        raise ValueError(f"Agent 目标配置合计超过 100%: {target_sum:.2f}%")

    news_codes = {
        str(item.get("fund_code", "")) for item in (news_data or []) if item.get("fund_code")
    }
    missing_news = sorted(news_codes - set(decisions.get("news") or {}))
    if missing_news:
        raise ValueError(f"Agent 决策未覆盖全部新闻研判对象: {', '.join(missing_news)}")
    for code in news_codes:
        _validate_news_decision(code, decisions["news"][code])
    candidate_codes = {
        str(item.get("code") or item.get("fund_code", ""))
        for item in (recommendation_candidates or [])
    }
    recommended_codes = {
        str(item.get("code") or item.get("fund_code", ""))
        for item in decisions["recommendations"]
    }
    if "" in recommended_codes:
        raise ValueError("Agent 推荐对象必须提供基金代码")
    unsupported = sorted(recommended_codes - candidate_codes)
    if unsupported:
        raise ValueError(f"Agent 最终推荐缺少本次候选证据: {', '.join(unsupported)}")
    return decisions


def _validate_fund_decision(code, baseline, decision):
    if not isinstance(decision, dict):
        raise ValueError(f"Agent 基金决策缺失或格式错误: {code}")
    final_scores = decision.get("final_scores")
    adjustments = decision.get("agent_adjustments")
    if not isinstance(final_scores, dict) or not isinstance(adjustments, dict):
        raise ValueError(f"Agent 基金决策缺少 final_scores/agent_adjustments: {code}")

    baseline_keys = {"macro": "macro_score", "meso": "meso_score", "micro": "micro_score"}
    for dimension, baseline_key in baseline_keys.items():
        final = final_scores.get(dimension)
        adjustment = adjustments.get(dimension)
        if not isinstance(final, (int, float)) or not isinstance(adjustment, (int, float)):
            raise ValueError(f"Agent 基金决策分项必须为数值: {code}.{dimension}")
        if not -10 <= adjustment <= 10:
            raise ValueError(f"Agent 调整分超出 [-10, +10]: {code}.{dimension}")
        base = baseline.get(baseline_key)
        if isinstance(base, (int, float)) and abs(final - (base + adjustment)) > 1e-6:
            raise ValueError(f"Agent 最终分无法与量化基准及调整分对账: {code}.{dimension}")

    final_total = final_scores.get("total")
    calculated_total = sum(final_scores[key] for key in ("macro", "meso", "micro"))
    if not isinstance(final_total, (int, float)) or abs(final_total - calculated_total) > 1e-6:
        raise ValueError(f"Agent 综合分无法与分项合计对账: {code}")
    if not 0 <= final_total <= 100:
        raise ValueError(f"Agent 综合分超出 [0, 100]: {code}")
    if not decision.get("final_action"):
        raise ValueError(f"Agent 基金决策缺少 final_action: {code}")
    if not isinstance(decision.get("rationale"), list) or not decision["rationale"]:
        raise ValueError(f"Agent 基金决策缺少 rationale: {code}")
    if not isinstance(decision.get("triggers"), list) or not decision["triggers"]:
        raise ValueError(f"Agent 基金决策缺少 triggers: {code}")
    for field in ("target_weight_pct", "adjust_amount"):
        if field not in decision:
            raise ValueError(f"Agent 基金决策缺少 {field}: {code}")
    target = decision.get("target_weight_pct")
    if target is not None and (not isinstance(target, (int, float)) or not 0 <= target <= 100):
        raise ValueError(f"Agent 目标占比超出 [0, 100]: {code}")

    for pct_field in ("suggested_stop_profit_pct", "suggested_stop_loss_pct"):
        val = decision.get(pct_field)
        if val is not None and not isinstance(val, (int, float)):
            raise ValueError(f"Agent {pct_field} 必须为数值: {code}")

    if decision.get("daily_attribution") is not None and not isinstance(decision.get("daily_attribution"), str):
        raise ValueError(f"Agent daily_attribution 必须为字符串: {code}")


def _validate_news_decision(code, decision):
    if not isinstance(decision, dict):
        raise ValueError(f"Agent 新闻研判缺失或格式错误: {code}")
    for field in ("summary", "impact", "relevance"):
        if not decision.get(field):
            raise ValueError(f"Agent 新闻研判缺少 {field}: {code}")
    confidence = decision.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError(f"Agent 新闻研判置信度必须在 [0, 1]: {code}")
    if "key_news" in decision:
        if not isinstance(decision["key_news"], list):
            raise ValueError(f"Agent 新闻研判 key_news 必须为列表: {code}")
        for item in decision["key_news"]:
            if not isinstance(item, dict) or "title" not in item or "reason" not in item:
                raise ValueError(f"Agent 新闻研判 key_news 内项目必须包含 title 和 reason: {code}")


def _build_report_evidence(
    report_date,
    scores,
    holdings_data,
    news_data,
    correlations,
    stress_results,
    portfolio_risk_matrix,
    recommendations=None,
    recommendation_status="skipped",
    workflow_context=None,
):
    """Build serializable evidence consumed by the fund-analyst Agent."""
    by_fund = (holdings_data or {}).get("by_fund", {})
    funds = {}
    daily_clues = {}

    for score in scores or []:
        code = score.get("fund_code")
        metrics = by_fund.get(code, {})
        news = next((item for item in (news_data or []) if item.get("fund_code") == code), {})
        funds[code] = {
            "identity": {
                "code": code,
                "name": score.get("fund_name"),
                "fund_type": score.get("fund_type"),
                "data_completeness": score.get("data_completeness"),
            },
            "holding_metrics": metrics,
            "quant_baseline": {
                "macro_score": score.get("macro_score"),
                "meso_score": score.get("meso_score"),
                "micro_score": score.get("micro_score"),
                "total_score": score.get("composite_score"),
                "score_confidence": score.get("score_confidence"),
            },
            "factor_matrix": score.get("factor_matrix") or {},
            "trend_evidence": score.get("trend_evidence") or {},
            "risk_constraints": score.get("risk_constraints") or {},
            "news_evidence": {
                "news_count": news.get("news_count", 0),
                "decayed_lexicon_signal": news.get("sentiment_mean"),
                "brief": news.get("brief") or {},
                "evaluation": news.get("news_evaluation") or {},
                "samples": (news.get("news_list") or [])[:10],
                "post_cutoff_news": news.get("post_cutoff_news") or [],
                "relevance_task": news.get("relevance_task") or {},
            },
        }

        daily_clues[code] = {
            "fund_name": score.get("fund_name"),
            "day_profit": metrics.get("day_profit"),
            "day_return_pct": metrics.get("day_return_pct"),
            "top_news_headlines": [n.get("title") for n in (news.get("news_list") or [])[:5]]
        }

    corr_payload = correlations.to_dict() if hasattr(correlations, "to_dict") else {}
    return {
        "schema_version": "report_evidence.v2",
        "report_date": report_date.isoformat(),
        "report_status": "awaiting_agent_decisions",
        "portfolio": {
            "total_value": (holdings_data or {}).get("total_value", 0),
            "total_cost": (holdings_data or {}).get("total_cost", 0),
            "total_profit": (holdings_data or {}).get("total_profit", 0),
            "daily_profit": (holdings_data or {}).get("total_day_profit", 0),
            "daily_return_pct": (holdings_data or {}).get("total_day_return_pct", 0),
            "daily_attribution_clues": daily_clues,
        },
        "funds": funds,
        "portfolio_evidence": {
            "correlations": corr_payload,
            "stress_tests": stress_results or [],
            "risk_matrix": portfolio_risk_matrix or {},
        },
        "workflow_evidence": {
            "dca_rows": (workflow_context or {}).get("dca_rows") or [],
            "settlement_rows": (workflow_context or {}).get("settlement_rows") or [],
            "top_news": (workflow_context or {}).get("top_news") or [],
        },
        "recommendation_evidence": {
            "status": recommendation_status,
            "candidates": recommendations or [],
        },
    }


def _write_report_evidence(output_path, evidence):
    import json
    import os

    base, ext = os.path.splitext(output_path)
    if base.endswith(".evidence"):
        base = base[:-9]
    path = f"{base}.evidence.json" if ext else f"{output_path}.evidence.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2, default=str)
    return path


def _attach_decision_evidence(scores, news_contexts, holdings_data):
    """Attach trend and position evidence without publishing an automatic action."""
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
        score["trend_evidence"] = trend
        score["risk_constraints"] = {
            "current_weight": round(position_context["current_weight"], 4),
            "pending_amount": position_context["pending_amount"],
            "is_qdii": position_context["is_qdii"],
            "dca_enabled": position_context["dca_enabled"],
            "requires_agent_decision": True,
        }


def _write_keyword_request_and_exit(config, codes, analyzer, output_path):
    """生成 .news_keywords_request.json 请求文件，引导 Agent 生成关键词缓存后安全退出"""
    import json
    import sys
    from src.news.news_fetcher import _cached_ak_call, _normalize_company_name, _pick_first

    request_file = output_path
    if request_file.endswith(".md"):
        request_file = request_file[:-3] + ".news_keywords_request.json"
    else:
        request_file = request_file + ".news_keywords_request.json"

    print(f"\n[CLI] 未找到有效的新闻关键词缓存，生成请求文件: {request_file}")

    funds_data = {}
    for code in codes:
        fund_data = analyzer.funds.get(code, {})
        basic = fund_data.get("basic", {})
        name = basic.get("name", code)
        fund_type = basic.get("fund_type", "")

        # 提取重仓持股
        top_holdings = []
        for year in ["2025", "2024"]:
            try:
                df = _cached_ak_call("fund_portfolio_hold_em", symbol=code, date=year)
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        stock_code = str(row.get("股票代码", "")).strip()
                        if not stock_code or stock_code.lower() == "nan":
                            continue
                        stock_name = _normalize_company_name(str(row.get("股票名称", "")))
                        weight = _pick_first(row, ["占净值比例", "持仓占比", "占比", "持股占比"])
                        top_holdings.append({
                            "stock_name": stock_name,
                            "stock_code": stock_code,
                            "weight": str(weight) if weight is not None else "",
                        })
                    break
            except Exception:
                continue

        funds_data[code] = {
            "name": name,
            "type": fund_type,
            "top_holdings": top_holdings
        }

    request_payload = {
        "request_version": "news_keyword_request.v1",
        "generated_at": _shared_today().isoformat(),
        "cache_path": "data/cache/news_keyword_profiles.json",
        "holding_codes": sorted(codes),
        "funds": funds_data
    }

    with open(request_file, "w", encoding="utf-8") as f:
        json.dump(request_payload, f, ensure_ascii=False, indent=2)

    print(f"[CLI] 请使用 Agent 为该请求文件生成对应的关键词缓存，然后重新运行。")
    sys.exit(0)


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

    settlement_rows = []
    for fund in (holdings_data or {}).get("funds", []):
        detail = by_fund.get(fund["code"], {})
        pending_events = [
            e for e in detail.get("engine_events", [])
            if e.get("type") == "BUY" and e.get("status") == "PENDING"
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
            "nav_status": "披露日期早于口径日" if detail.get("nav_date", "") and detail.get("nav_date", "") < report_date.isoformat() else "口径日已覆盖",
            "settle_delay": settle_delay,
            "settlement_status": "有待确认交易" if pending_events or detail.get("pending_amount", 0) > 0 else "已确认",
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


def _run_news_analysis(config, analyzer, agent_news_plan=None, report_date=None):
    """运行新闻分析 —— 持仓驱动定向采集 → 去重 → 蒸馏 → 简报"""
    from src.news.pipeline import run_news_pipeline
    return run_news_pipeline(
        analyzer, config, agent_news_plan, days=7, report_date=report_date
    )


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
        # Persist new neutral evidence in the legacy JSON column for backward-compatible snapshots.
        "trend_matrix": s.get("trend_evidence") or s.get("trend_matrix"),
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
    import pandas as pd

    code = args.code
    analyzer = FundAnalyzer()
    analyzer.load_fund(code)

    if code not in analyzer.funds or analyzer.funds[code]["completeness"] == "D":
        print(f"[ERROR] 无法获取 {code} 的足够数据")
        return

    s = analyzer.score_fund(code)
    
    # 提取最新单位净值和当日变动
    nav_df = analyzer.funds[code].get("nav")
    latest_nav = None
    latest_nav_date = None
    latest_return = None
    if isinstance(nav_df, pd.DataFrame) and not nav_df.empty:
        nav_df_sorted = nav_df.sort_index()
        latest_date = nav_df_sorted.index[-1]
        latest_nav_date = latest_date.date() if hasattr(latest_date, 'date') else latest_date
        latest_nav = float(nav_df_sorted.loc[latest_date, "单位净值"])
        if "日增长率" in nav_df_sorted.columns:
            latest_return = float(nav_df_sorted.loc[latest_date, "日增长率"])

    # 映射中文字段名称
    CHINESE_FACTOR_NAMES = {
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

    def format_value(key, val):
        if val is None or val == "":
            return "N/A"
        try:
            f_val = float(val)
            if key in ("max_drawdown_3y_pct", "annual_volatility"):
                # 如果最大回撤已带负号，不要重复添加
                if key == "max_drawdown_3y_pct" and f_val > 0:
                    return f"-{f_val:.2f}%"
                return f"{f_val:.2f}%"
            elif key in ("jensen_alpha", "beta", "sortino_ratio", "sharpe_1y", "information_ratio"):
                return f"{f_val:.4f}" if key == "jensen_alpha" else f"{f_val:.2f}"
            elif key == "hhi_index":
                return f"{f_val:.4f}"
            else:
                return str(val)
        except (ValueError, TypeError):
            return str(val)

    # 打印高端投研报告排版
    print("=" * 80)
    print("                    公募基金量化分析与深度诊断报告")
    print("=" * 80)
    print(" 【基金基本信息】")
    print(f"   - 基金名称: {s['fund_name']}")
    print(f"   - 基金代码: {code}")
    print(f"   - 基金类型: {s.get('fund_type', 'N/A')} | 基金经理: {s.get('manager', 'N/A')}")
    print(f"   - 数据完整度: {s['data_completeness']}  | 诊断置信度: {int(s.get('score_confidence', 0.5) * 100)}%")
    print()
    print(" 【最新业绩表现】")
    nav_str = f"{latest_nav:.4f}" if latest_nav is not None else "N/A"
    date_str = latest_nav_date.isoformat() if latest_nav_date else "N/A"
    return_str = f"{latest_return:+.2f}%" if latest_return is not None else "N/A"
    print(f"   - 最新单位净值: {nav_str} ({date_str}) | 当日涨跌幅: {return_str}")
    print(f"   - 历史最大回撤 (3年): {format_value('max_drawdown_3y_pct', s.get('max_drawdown_3y'))}")
    print(f"   - 年化波动率 (1年): {format_value('annual_volatility', s.get('annual_volatility'))}")
    
    fm = s.get("feature_matrix", {})
    print(f"   - 夏普比率 (1年): {format_value('sharpe_1y', fm.get('sharpe_1y'))} | 索提诺比率: {format_value('sortino_ratio', fm.get('sortino_ratio'))}")
    print(f"   - 詹森 Alpha: {format_value('jensen_alpha', fm.get('jensen_alpha'))} | 系统 Beta: {format_value('beta', fm.get('beta'))} | 持仓集中度(HHI): {format_value('hhi_index', fm.get('hhi_index'))}")
    print()
    print("=" * 80)
    print(f" 基金综合评分: {s['composite_score']} / 100  （{s['score_level_emoji']} {s['score_tendency']}）")
    print("=" * 80)
    print(f" 评分建议: {s['recommendation']}")
    print(f" 止盈触发线: +{s['stop_profit_pct']:.2f}% | 止损保护线: {s['stop_loss_pct']:.2f}%")
    print(f" 宏观得分: {s['macro_score']}/20 | 中观得分: {s.get('meso_score') or 0}/30 | 微观得分: {s['micro_score']}/50")
    print(f" 评分依据: {s['action_logic']}")
    print("-" * 80)
    print(" 评分性质: 规则种子分；最终评定请由接入 skill 的 agent 结合事件研判校准。")
    print()
    
    # 打印因子打分拆解树状图
    print(" 【因子打分拆解 (定量因子矩阵)】")
    factors = s.get("factor_matrix", {})
    
    # 1. 宏观
    macro_score_val = float(s['macro_score'])
    print(f" ├─ 宏观维度 (得分: {macro_score_val:.2f} / 20.00 分)")
    macro_factors = factors.get("macro", [])
    for idx, f in enumerate(macro_factors):
        is_last = (idx == len(macro_factors) - 1)
        prefix = " │  └─" if is_last else " │  ├─"
        name_zh = CHINESE_FACTOR_NAMES.get(f['name'], f['name'])
        val_str = format_value(f['name'], f['value'])
        weight_pct = f['weight'] * 100
        factor_score = f['score'] * 100
        actual_points = f['weight'] * f['score'] * 100
        max_points = f['weight'] * 100
        print(f"{prefix} {name_zh} ({f['name']})")
        print(f" │     [值: {val_str} | 因子打分: {factor_score:.2f}% | 实际得分: {actual_points:.2f} / {max_points:.2f} 分]")
    print(" │")
    
    # 2. 中观
    meso_score_val = float(s.get('meso_score') or 0)
    print(f" ├─ 中观维度 (得分: {meso_score_val:.2f} / 30.00 分)")
    meso_factors = factors.get("meso", [])
    for idx, f in enumerate(meso_factors):
        is_last = (idx == len(meso_factors) - 1)
        prefix = " │  └─" if is_last else " │  ├─"
        name_zh = CHINESE_FACTOR_NAMES.get(f['name'], f['name'])
        val_str = format_value(f['name'], f['value'])
        weight_pct = f['weight'] * 100
        factor_score = f['score'] * 100
        actual_points = f['weight'] * f['score'] * 100
        max_points = f['weight'] * 100
        print(f"{prefix} {name_zh} ({f['name']})")
        print(f" │     [值: {val_str} | 因子打分: {factor_score:.2f}% | 实际得分: {actual_points:.2f} / {max_points:.2f} 分]")
    print(" │")
    
    # 3. 微观
    micro_score_val = float(s['micro_score'])
    print(f" └─ 微观维度 (得分: {micro_score_val:.2f} / 50.00 分)")
    micro_factors = factors.get("micro", [])
    for idx, f in enumerate(micro_factors):
        is_last = (idx == len(micro_factors) - 1)
        prefix = "    └─" if is_last else "    ├─"
        name_zh = CHINESE_FACTOR_NAMES.get(f['name'], f['name'])
        val_str = format_value(f['name'], f['value'])
        weight_pct = f['weight'] * 100
        factor_score = f['score'] * 100
        actual_points = f['weight'] * f['score'] * 100
        max_points = f['weight'] * 100
        print(f"{prefix} {name_zh} ({f['name']})")
        print(f"       [值: {val_str} | 因子打分: {factor_score:.2f}% | 实际得分: {actual_points:.2f} / {max_points:.2f} 分]")
    print("=" * 80)


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
    p_analyze.add_argument(
        "--fallback-keywords",
        action="store_true",
        help="当缺失新闻关键词缓存时，自动使用重仓股和行业词作为兜底，并缓存，而不是生成请求并退出",
    )
    p_analyze.add_argument(
        "--agent-decisions",
        default=None,
        help="与本次 evidence 口径日一致的 Agent 最终决策 JSON；提供后生成最终报告",
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
