"""Contracts for front-loaded agent decisions.

The Python pipeline collects evidence and requests decisions. The fund-analyst
skill agent fills these decisions before the final report is rendered.
"""
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentDecisionRequest(BaseModel):
    request_version: str = "agent_decision_request.v1"
    instructions: List[str] = Field(default_factory=list)
    portfolio_snapshot: Dict[str, Any] = Field(default_factory=dict)
    fund_score_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    news_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    stress_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation_task: Dict[str, Any] = Field(default_factory=dict)
    expected_decision_schema: Dict[str, Any] = Field(default_factory=dict)


class AgentDecisionSet(BaseModel):
    decision_version: str = "agent_decision_set.v1"
    portfolio: Dict[str, Any] = Field(default_factory=dict)
    fund_scores: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    news: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    stress_tests: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_notes: List[str] = Field(default_factory=list)


class AgentNewsSearchPlan(BaseModel):
    plan_version: str = "agent_news_search_plan.v1"
    funds: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    portfolio_lenses: List[str] = Field(default_factory=list)
    evidence_notes: List[str] = Field(default_factory=list)


def news_search_plan_schema_hint() -> Dict[str, Any]:
    return {
        "plan_version": "agent_news_search_plan.v1",
        "funds": {
            "基金代码": {
                "keywords": ["重仓公司", "产业链关键词", "政策/资金关键词"],
                "research_lenses": ["为什么这些词会影响净值"],
                "exclude_keywords": ["明显无关或噪音词"],
                "rationale": "基于重仓、占比、基金类型推导搜索范围",
            }
        },
        "portfolio_lenses": ["组合共振风险或跨基金主题"],
        "evidence_notes": ["缺失数据或不确定性"],
    }


def build_news_search_request(
    portfolio_context: Dict[str, Any],
    fund_profiles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "request_version": "agent_news_search_request.v1",
        "instructions": [
            "这是新闻抓取前的检索计划请求，不是新闻总结任务。",
            "请基于基金真实重仓、持仓占比、基金类型和用户仓位，先决定要搜索哪些公司、产业链、政策、资金和估值关键词。",
            "代码给出的 holding_keywords/fallback_keywords 只是证据和兜底；请补充更贴近基金实际风险敞口的关键词。",
            "避免只按基金名称、半导体/新能源等宽泛词机械检索；每只基金给出 5-12 个高价值关键词即可。",
        ],
        "portfolio_snapshot": portfolio_context,
        "fund_profiles": fund_profiles,
        "expected_plan_schema": news_search_plan_schema_hint(),
    }


def decision_schema_hint() -> Dict[str, Any]:
    return {
        "decision_version": "agent_decision_set.v1",
        "portfolio": {
            "tldr": "最终组合一句话结论",
            "stance": "加仓/持有/降风险/等待",
            "key_actions": ["动作1", "动作2"],
            "risk_focus": ["风险1", "风险2"],
        },
        "fund_scores": {
            "基金代码": {
                "final_score": 0,
                "level": "green/yellow/orange/red",
                "macro_score": 0,
                "meso_score": 0,
                "micro_score": 0,
                "recommendation": "持有/加仓/暂停定投/减仓/替换",
                "rationale": ["依据1", "依据2"],
                "action": "具体动作",
                "triggers": ["观察条件1", "观察条件2"],
            }
        },
        "news": {
            "基金代码": {
                "summary": "事件归因",
                "impact": "positive/neutral/negative/mixed",
                "relevance": "high/medium/low",
                "watch_items": ["观察项"],
            }
        },
        "stress_tests": [
            {
                "scenario": "当前最相关风险情景",
                "affected_funds": ["基金代码"],
                "impact_range_pct": [-10, -5],
                "impact_amount_range": [-3000, -1500],
                "confidence": "high/medium/low",
                "action": "应对动作",
            }
        ],
        "recommendations": [
            {
                "code": "基金代码",
                "name": "基金名称",
                "portfolio_role": "组合角色",
                "reason": "为什么推荐",
                "why_not_same_theme": "为什么没有选择同类扎堆基金",
                "buy_method": "定投/小额试仓/观察",
                "risks": ["风险1"],
            }
        ],
    }


def build_agent_decision_request(
    portfolio_context: Dict[str, Any],
    scores: List[Dict[str, Any]],
    news_data: List[Dict[str, Any]],
    stress_tests: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
    recommendation_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    safe_recommendations = [
        _json_safe(rec, drop_keys={"agent_recommendation_context"})
        for rec in (recommendations or [])
    ]
    safe_recommendation_context = _json_safe(
        recommendation_context or {},
        drop_keys={"agent_recommendation_context"},
    )
    return AgentDecisionRequest(
        instructions=[
            "这是最终报告渲染前的前置决策请求，不是报告摘要任务。",
            "请在此阶段完成评分校准、新闻相关性判断、时事压力测试、组合增益推荐。",
            "代码只提供证据与规则初稿；最终内容应由 agent 直接生成。",
        ],
        portfolio_snapshot=portfolio_context,
        fund_score_tasks=[
            {
                "fund_code": s.get("fund_code"),
                "fund_name": s.get("fund_name"),
                "rule_score_seed": {
                    "composite_score": s.get("composite_score"),
                    "macro_score": s.get("macro_score"),
                    "meso_score": s.get("meso_score"),
                    "micro_score": s.get("micro_score"),
                    "recommendation": s.get("recommendation"),
                    "action_logic": s.get("action_logic"),
                },
                "fund_context": s.get("agent_score_context", {}).get("fund_context", {}),
            }
            for s in scores or []
        ],
        news_tasks=[
            {
                "fund_code": n.get("fund_code"),
                "fund_name": n.get("fund_name"),
                "news_count": n.get("news_count"),
                "events": n.get("events", []),
                "daily_aggregates": n.get("daily_aggregates", []),
                "sample_news": [
                    {
                        "title": item.get("title"),
                        "content": item.get("content", "")[:260],
                        "sentiment_score": item.get("sentiment_score"),
                        "source": item.get("source"),
                        "date": item.get("date"),
                    }
                    for item in (n.get("news_list", []) or [])[:8]
                ],
                "agent_news_context": n.get("agent_news_context", {}),
            }
            for n in news_data or []
        ],
        stress_tasks=stress_tests or [],
        recommendation_task={
            "candidate_recommendations": safe_recommendations,
            "recommendation_context": safe_recommendation_context,
        },
        expected_decision_schema=decision_schema_hint(),
    ).model_dump(mode="json")


def build_agent_evidence_pack(
    report_date: Any,
    portfolio_context: Dict[str, Any],
    workflow_context: Dict[str, Any],
    scores: List[Dict[str, Any]],
    holdings_data: Dict[str, Any],
    news_data: List[Dict[str, Any]],
    stress_results: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the single process artifact consumed by the fund-analyst skill."""
    return _json_safe({
        "pack_version": "agent_evidence_pack.v1",
        "instructions": [
            "这是唯一过程数据文件。当前 agent 读取后直接输出最终基金分析报告，不再生成新闻计划或决策过程 JSON。",
            "脚本数据是证据包和规则初稿；最终评分、新闻归因、压力测试和推荐必须由 agent 按 skill 判断。",
            "不要编造缺失数据；对净值日期、QDII 延迟、pending 和交易流水口径要明确标注。",
        ],
        "report_tasks": [
            "校准每只基金评分和操作建议",
            "结合新闻事件、重仓和净值变化做归因",
            "构造当前最相关的组合压力测试",
            "筛选少而精的推荐或替代基金",
            "按 fund-analyst skill 的报告格式输出最终分析报告",
        ],
        "data": {
            "report_date": report_date.isoformat() if hasattr(report_date, "isoformat") else str(report_date),
            "portfolio_snapshot": portfolio_context,
            "workflow_context": workflow_context,
            "holdings_data": holdings_data or {},
            "score_seeds": scores or [],
            "news_data": news_data or [],
            "stress_seed": stress_results or [],
            "recommendation_candidates": recommendations or [],
        },
        "final_report_format": [
            "组合结论",
            "关键动作",
            "评分解释",
            "新闻和归因",
            "压力测试",
            "推荐/替代",
            "监控清单",
        ],
        "decision_schema_reference": decision_schema_hint(),
    })


def validate_agent_decisions(payload: Dict[str, Any]) -> Dict[str, Any]:
    return AgentDecisionSet.model_validate(payload).model_dump(mode="json")


def validate_agent_news_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    return AgentNewsSearchPlan.model_validate(payload).model_dump(mode="json")


def _json_safe(value: Any, drop_keys: set = None, seen: set = None) -> Any:
    drop_keys = drop_keys or set()
    seen = seen or set()
    if isinstance(value, dict):
        obj_id = id(value)
        if obj_id in seen:
            return None
        seen.add(obj_id)
        result = {
            k: _json_safe(v, drop_keys=drop_keys, seen=seen)
            for k, v in value.items()
            if k not in drop_keys
        }
        seen.remove(obj_id)
        return result
    if isinstance(value, list):
        obj_id = id(value)
        if obj_id in seen:
            return []
        seen.add(obj_id)
        result = [_json_safe(item, drop_keys=drop_keys, seen=seen) for item in value]
        seen.remove(obj_id)
        return result
    return value
