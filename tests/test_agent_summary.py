from datetime import date
import json

import pandas as pd

from src.agents.protocols import AgentOpinion
from src.agents.summary import compose_agent_decisions
from src.core.contracts import load_agent_decisions
from src.output.report import generate_report
from src.output.validator import validate_final_report


def test_summary_composes_opinions_into_valid_agent_decisions(tmp_path):
    evidence = {
        "report_date": "2026-05-22",
        "funds": {
            "000001": {
                "quant_baseline": {"macro_score": 15, "meso_score": 22, "micro_score": 39}
            }
        },
    }
    opinions = [
        AgentOpinion(
            agent="news",
            payload={
                "fund_code": "000001",
                "summary": "新闻覆盖有限但相关",
                "impact": "neutral",
                "relevance": "medium",
                "confidence": 0.6,
                "watch": ["下一次公告后复核"],
            },
        ),
        AgentOpinion(
            agent="scoring",
            payload={
                "fund_code": "000001",
                "agent_adjustments": {"macro": 1, "meso": 0, "micro": 0},
                "final_scores": {"macro": 16, "meso": 22, "micro": 39, "total": 77},
                "rationale": ["宏观流动性边际改善，但新闻覆盖仍有限"],
                "triggers": ["若同类指数回撤超过 5% 则复核"],
                "trend_view": "短期中性",
                "suggested_stop_profit_pct": 25.0,
                "suggested_stop_loss_pct": -15.0,
            },
        ),
        AgentOpinion(
            agent="portfolio",
            payload={
                "stance": "neutral",
                "tldr": "维持均衡",
                "risk_summary": ["组合集中度可控"],
                "execution_notes": ["不新增 pending"],
                "daily_analysis": "组合当日归因中性。",
                "fund_targets": {
                    "000001": {
                        "final_action": "hold",
                        "target_weight_pct": 18.0,
                        "adjust_amount": 0,
                        "triggers": ["若同类指数回撤超过 5% 则复核"],
                    }
                },
                "recommendations": [],
            },
        ),
    ]

    decisions = compose_agent_decisions(evidence, opinions)
    path = tmp_path / "agent_decisions.json"
    path.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")

    loaded = load_agent_decisions(
        str(path),
        date(2026, 5, 22),
        scores=[{
            "fund_code": "000001",
            "macro_score": 15,
            "meso_score": 22,
            "micro_score": 39,
        }],
        news_data=[{"fund_code": "000001"}],
        recommendation_candidates=[],
    )

    assert loaded["schema_version"] == "agent_decisions.v2"
    assert loaded["fund_scores"]["000001"]["final_scores"]["total"] == 77
    assert loaded["news"]["000001"]["relevance"] == "medium"


def test_summary_composed_decisions_render_valid_final_report(tmp_path):
    score = {
        "fund_code": "000001",
        "fund_name": "测试基金",
        "macro_score": 15,
        "meso_score": 22,
        "micro_score": 39,
        "composite_score": 76,
        "data_completeness": "A",
        "stop_profit_pct": 20,
        "stop_loss_pct": -15,
    }
    evidence = {
        "report_date": "2026-05-22",
        "funds": {"000001": {"quant_baseline": score}},
    }
    opinions = [
        AgentOpinion(
            agent="news",
            payload={
                "fund_code": "000001",
                "summary": "无重大负面新闻",
                "impact": "neutral",
                "relevance": "medium",
                "confidence": 0.6,
            },
        ),
        AgentOpinion(
            agent="scoring",
            payload={
                "fund_code": "000001",
                "agent_adjustments": {"macro": 1, "meso": 0, "micro": 0},
                "final_scores": {"macro": 16, "meso": 22, "micro": 39, "total": 77},
                "rationale": ["宏观流动性边际改善"],
                "triggers": ["若同类指数回撤超过 5% 则复核"],
            },
        ),
        AgentOpinion(
            agent="portfolio",
            payload={
                "stance": "neutral",
                "tldr": "维持均衡",
                "daily_analysis": "组合当日归因中性。",
                "fund_targets": {
                    "000001": {
                        "final_action": "hold",
                        "target_weight_pct": 18.0,
                        "adjust_amount": 0,
                        "triggers": ["若同类指数回撤超过 5% 则复核"],
                    }
                },
                "recommendations": [],
            },
        ),
    ]
    decisions = compose_agent_decisions(evidence, opinions)
    path = tmp_path / "agent_decisions.json"
    path.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
    loaded = load_agent_decisions(
        str(path),
        date(2026, 5, 22),
        scores=[score],
        news_data=[{"fund_code": "000001"}],
        recommendation_candidates=[],
    )

    report = generate_report(
        None,
        [score],
        pd.DataFrame(),
        [],
        agent_decisions=loaded,
    )

    validate_final_report(report, "2026-05-22", 0)
    assert "Agent 最终研判" in report
    assert "77/100" in report


def test_summary_requires_scoring_opinion_for_each_fund():
    evidence = {"report_date": "2026-05-22", "funds": {"000001": {}}}
    opinions = [AgentOpinion(agent="portfolio", payload={"stance": "neutral", "tldr": "测试"})]

    try:
        compose_agent_decisions(evidence, opinions)
    except ValueError as exc:
        assert "缺少 scoring opinion" in str(exc)
    else:
        raise AssertionError("missing scoring opinion should fail")
