"""新闻催化分析模块 —— LLM 事件蒸馏 + 严重度/影响度 + 时间衰减权重

分层策略：
1. 规则层（词典/关键词匹配）—— 快速、低成本，处理 80% 的常规新闻
2. LLM 层 —— 仅对高价值新闻（公告、财报、重大事件）做深度蒸馏
"""
import json
import numpy as np
import urllib.request
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

from legacy.news.schemas import LLM_CONFIG
from src.infra.config.defaults import QUANT_CONFIG


# ============================================================
# 事件类型字典（规则层）
# ============================================================

_EVENT_PATTERNS = [
    # (事件类型, 极性, 关联词列表)
    ("业绩超预期", 1, ["超预期", "业绩增长", "净利润增", "营收增", "同比增", "环比增"]),
    ("业绩不及预期", -1, ["不及预期", "业绩下滑", "净利润降", "营收降", "亏损", "利润降"]),
    ("订单增长", 1, ["新订单", "订单增", "中标", "签约", "合同", "获订单"]),
    ("订单下修", -1, ["订单下修", "取消订单", "订单减少", "需求疲软"]),
    ("CAPEX扩张", 1, ["扩产", "资本开支", "建厂", "产能扩张", "投资建"]),
    ("去库存", -1, ["去库存", "库存积压", "消化库存", "降价去库"]),
    ("涨价", 1, ["涨价", "提价", "价格上调", "供不应求"]),
    ("降价", -1, ["降价", "价格下调", "价格战", "促销"]),
    ("减产", -1, ["减产", "停产", "限产", "关停"]),
    ("政策利好", 1, ["政策支持", "补贴", "利好政策", "扶持", "减税", "降准"]),
    ("政策利空", -1, ["政策收紧", "监管", "处罚", "调查", "限制", "加税"]),
    ("回购/增持", 1, ["回购", "增持", "股东增持", "高管增持"]),
    ("减持", -1, ["减持", "股东减持", "套现"]),
    ("产品发布", 1, ["发布", "上市", "推出", "首款", "亮相", "新品"]),
    ("技术突破", 1, ["突破", "攻克", "自主研发", "量产", "认证"]),
    ("风险提示", -1, ["风险提示", "退市", "ST", "停牌", "警示"]),
    ("裁员/降本", -1, ["裁员", "降薪", "缩减", "降本", "优化"]),
]


def _rule_event_distill(text: str) -> dict | None:
    """规则层事件蒸馏 —— 基于关键词匹配。

    Returns:
        {"event_type": str, "polarity": int, "severity": float} 或 None
    """
    if not text:
        return None

    matches = []
    for event_type, polarity, keywords in _EVENT_PATTERNS:
        hit_count = sum(1 for kw in keywords if kw in text)
        if hit_count > 0:
            severity = min(1.0, 0.4 + 0.2 * hit_count)
            matches.append({
                "event_type": event_type,
                "polarity": polarity,
                "severity": severity,
                "hit_count": hit_count,
            })

    if not matches:
        return None

    # 返回命中最多的事件
    matches.sort(key=lambda m: -m["hit_count"])
    best = matches[0]
    return {
        "event_type": best["event_type"],
        "polarity": best["polarity"],
        "severity": round(best["severity"], 4),
    }


def _llm_event_distill(title: str, content: str = "") -> dict | None:
    """LLM 层事件蒸馏 —— 调用模型解析新闻事件。

    LLM 失败时静默降级，不阻塞主流程。
    """
    if not title:
        return None

    prompt = (
        "你是一个金融新闻分析师。请从以下新闻中提取事件信息，返回严格的 JSON 格式。\n\n"
        f"标题：{title[:200]}\n"
        f"内容：{content[:400] if content else '无'}\n\n"
        "请返回 JSON（不要 Markdown 代码块，只返回纯 JSON）：\n"
        "{\n"
        '  "event_type": "事件类型",\n'
        '  "polarity": 1或-1或0,\n'
        '  "severity": 0.0-1.0,\n'
        '  "summary": "一句话概述"\n'
        "}\n"
        "事件类型可选：业绩超预期/业绩不及预期/订单增长/订单下修/CAPEX扩张/去库存/"
        "涨价/降价/减产/扩产/政策利好/政策利空/回购增持/减持/产品发布/技术突破/"
        "风险提示/裁员降本/其他"
    )

    try:
        data = json.dumps({
            "model": LLM_CONFIG["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": LLM_CONFIG["max_tokens"],
            "temperature": LLM_CONFIG["temperature"],
        }).encode("utf-8")

        req = urllib.request.Request(
            LLM_CONFIG["api_url"],
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
                "User-Agent": "fund-agent/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=LLM_CONFIG["timeout"]) as resp:
            raw = json.loads(resp.read().decode())
            content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content.strip())
            return {
                "event_type": str(result.get("event_type", "其他")),
                "polarity": int(result.get("polarity", 0)),
                "severity": float(result.get("severity", 0.5)),
                "summary": str(result.get("summary", "")),
            }
    except Exception:
        return None  # LLM 失败时降级，规则层兜底


def distill_event(
    title: str,
    content: str = "",
    use_llm: bool = False,
) -> Dict:
    """统一事件蒸馏入口 —— LLM优先，规则兜底。

    Args:
        title: 新闻标题
        content: 新闻内容
        use_llm: 是否启用 LLM（高价值新闻才传 True）

    Returns:
        {"event_type": str, "polarity": int, "severity": float, "summary": str}
    """
    # 第一层：LLM 蒸馏（仅对高价值新闻且启用时优先）
    if use_llm:
        llm_result = _llm_event_distill(title, content)
        if llm_result:
            return llm_result

    # 第二层：规则匹配
    rule_result = _rule_event_distill(title + " " + (content or ""))
    if rule_result:
        return {**rule_result, "summary": ""}

    # 兜底
    return {
        "event_type": "其他",
        "polarity": 0,
        "severity": 0.3,
        "summary": "",
    }


# ============================================================
# 相关度 + 时间衰减 + 催化评分
# ============================================================


def compute_relevance(
    news_item: Dict,
    entity_profile,
    stock_hit_weight: float = 0.4,
    sector_hit_weight: float = 0.3,
    keyword_hit_weight: float = 0.3,
) -> float:
    """计算新闻与基金持仓的相关度 (0-1)。

    relevance = stock_hit * 0.4 + sector_hit * 0.3 + keyword_hit * 0.3
    """
    text = (news_item.get("title", "") or "") + " " + (news_item.get("content", "") or "")

    # 股票命中
    stock_hit = 0.0
    stock_names = getattr(entity_profile, "stock_names", [])
    if stock_names:
        hits = sum(1 for name in stock_names if name in text)
        stock_hit = min(1.0, hits / max(1, len(stock_names)) * 2)

    # 行业命中
    sector_hit = 0.0
    sector_kw = getattr(entity_profile, "sector_keywords", [])
    if sector_kw:
        hits = sum(1 for kw in sector_kw if kw in text)
        sector_hit = min(1.0, hits / max(1, len(sector_kw)) * 2)

    # 关键词命中
    kw_hit = 0.0
    theme_kw = getattr(entity_profile, "theme_keywords", [])
    if theme_kw:
        hits = sum(1 for kw in theme_kw if kw in text)
        kw_hit = min(1.0, hits / max(1, len(theme_kw)) * 2)

    return round(stock_hit * stock_hit_weight + sector_hit * sector_hit_weight + kw_hit * keyword_hit_weight, 4)


def compute_catalyst_score(
    news_items: list[Dict],
    entity_profile,
    today=None,
    lam: float = None,
) -> list[Dict]:
    """对一组新闻计算催化评分（含事件蒸馏 + 相关度 + 时间衰减）。

    weighted_score = severity × impact × relevance × exp(-λ × Δt)

    Args:
        news_items: 新闻列表（需含 title/content/date 字段）
        entity_profile: EntityProfile 对象
        today: 基准日期
        lam: 时间衰减系数 λ

    Returns:
        新闻列表，每项附加 catalyst 字段
    """
    if lam is None:
        lam = QUANT_CONFIG.get("NEWS_LAMBDA", 0.200)
    if today is None:
        today = datetime.now().date()

    enriched = []
    for item in news_items:
        title = item.get("title", "")
        content = item.get("content", "")

        # 判断是否高价值新闻（公告/财报类）
        is_high_value = any(
            kw in (title + content)
            for kw in ["公告", "财报", "业绩", "回购", "减持", "增持", "处罚", "监管"]
        )

        # 事件蒸馏
        event = distill_event(title, content, use_llm=is_high_value)

        # 影响范围
        impact = 1.0 if is_high_value else (0.5 if event["severity"] > 0.6 else 0.3)

        # 相关度
        relevance = compute_relevance(item, entity_profile)

        # 时间衰减
        date_str = item.get("date", "") or item.get("publish_date", "") or ""
        try:
            pub_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
            delta_t = (today - pub_date).days
        except Exception:
            delta_t = 1
        decay_weight = np.exp(-lam * max(0, delta_t))

        # 综合催化分
        weighted = round(
            event["severity"] * event["polarity"] * impact * relevance * decay_weight,
            4,
        )

        enriched.append({
            **item,
            "catalyst": {
                "event_type": event["event_type"],
                "polarity": event["polarity"],
                "severity": event["severity"],
                "impact": impact,
                "relevance": relevance,
                "decay_weight": round(decay_weight, 4),
                "weighted_score": weighted,
                "summary": event.get("summary", ""),
            },
        })

    return enriched


def aggregate_fund_brief(
    fund_code: str,
    fund_name: str,
    catalyst_news: list[Dict],
    date_str: str = "",
) -> Dict:
    """将多条新闻的催化评分聚合为基金级简报。

    Returns:
        FundNewsBrief 兼容的 dict
    """
    if not catalyst_news:
        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "date": date_str,
            "total_news": 0,
            "weighted_catalyst_score": 0.0,
            "trend": "neutral",
            "top_events": [],
            "sector_summary": {},
            "warnings": [],
        }

    # 总催化分 = 各条新闻加权分的均值
    scores = [n["catalyst"]["weighted_score"] for n in catalyst_news]
    avg_catalyst = round(float(np.mean(scores)), 4) if scores else 0.0

    # 趋势判定
    if avg_catalyst > 0.15:
        trend = "bullish"
    elif avg_catalyst < -0.15:
        trend = "bearish"
    else:
        trend = "neutral"

    # Top events（按绝对催化分排序）
    sorted_news = sorted(
        catalyst_news,
        key=lambda n: -abs(n["catalyst"]["weighted_score"]),
    )
    top_events = []
    for n in sorted_news[:5]:
        top_events.append({
            "title": n.get("title", ""),
            "entity": n.get("entity_hits", [""])[0] if n.get("entity_hits") else "",
            "event_type": n["catalyst"]["event_type"],
            "score": n["catalyst"]["weighted_score"],
            "summary": n["catalyst"].get("summary", ""),
        })

    # 行业热力图
    sector_map = defaultdict(float)
    for n in catalyst_news:
        for sector in n.get("sector_hits", []) or []:
            sector_map[sector] += n["catalyst"]["weighted_score"]

    # 警告
    warnings = []
    negative_count = sum(1 for n in catalyst_news if n["catalyst"]["weighted_score"] < -0.3)
    if negative_count >= 3:
        warnings.append(f"存在 {negative_count} 条高负向催化事件，请关注持仓风险")

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "date": date_str,
        "total_news": len(catalyst_news),
        "weighted_catalyst_score": avg_catalyst,
        "trend": trend,
        "top_events": top_events,
        "sector_summary": dict(sector_map),
        "warnings": warnings,
    }
