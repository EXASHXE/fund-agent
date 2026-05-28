"""
多因子基金推荐引擎。

流程：
  1. 从近期新闻提取热点行业
  2. 全市场基金筛选（收益动量 + 申购状态）
  3. 对候选基金计算多维相似度：行业/主题、风格、收益风险
  4. 综合排序：收益机会 + 热点 + 分散度 + 多样性约束
"""
from collections import Counter
from math import ceil
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class RecommendationCandidate(BaseModel):
    code: str
    name: str
    type: str = ""
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    size: Optional[float] = None
    theme: str = "其他"
    style_tags: list[str] = Field(default_factory=list)
    avg_similarity: float = 0.0
    max_similarity: float = 0.0
    sector_similarity: float = 0.0
    style_similarity: float = 0.0
    return_similarity: float = 0.0
    heat_score: float = 0.0
    momentum_score: float = 0.0
    diversification_score: float = 1.0
    exposure_cluster: str = "balanced_other"
    portfolio_role: str = "待判断"
    marginal_benefit: float = 0.0
    score: float = 0.0
    reason: str = ""
    risks: list[str] = Field(default_factory=list)


THEME_KEYWORDS = {
    "美股科技": ["纳斯达克", "标普", "美股", "科技", "互联网", "AI", "人工智能", "英伟达", "海外科技"],
    "新兴市场": ["新兴市场", "印度", "越南", "东南亚", "全球"],
    "能源商品": ["石油", "原油", "天然气", "能源", "油气", "商品"],
    "新能源": ["新能源", "电池", "锂电", "光伏", "储能", "电动车", "汽车"],
    "医药医疗": ["医药", "医疗", "创新药", "生物", "健康"],
    "消费": ["消费", "食品", "饮料", "白酒", "家电"],
    "金融地产": ["银行", "证券", "保险", "金融", "地产", "房地产"],
    "半导体": ["半导体", "芯片", "电子"],
    "宽基指数": ["沪深300", "中证500", "中证1000", "创业板", "上证50", "宽基"],
    "债券固收": ["债券", "纯债", "固收", "货币", "短债"],
    "红利价值": ["红利", "低波", "价值", "股息"],
}

STYLE_KEYWORDS = {
    "growth": ["成长", "科技", "新能源", "创业板", "AI", "人工智能", "半导体"],
    "value": ["价值", "红利", "低波", "银行", "股息"],
    "large_cap": ["沪深300", "上证50", "大盘", "蓝筹"],
    "mid_small_cap": ["中证500", "中证1000", "中小盘", "创业板"],
    "overseas": ["QDII", "纳斯达克", "标普", "全球", "海外", "新兴市场"],
    "commodity": ["石油", "黄金", "商品", "天然气"],
    "defensive": ["债券", "固收", "货币", "低波"],
}


# ------------------------------------------------------------
# 原子化产业关键词白名单（精确匹配，从旧 sentiment 模块内联）
# ------------------------------------------------------------
_ATOMIC_INDUSTRY_KEYWORDS = [
    # 半导体
    "半导体", "芯片", "光刻机", "光刻胶", "晶圆", "封装", "HBM", "NAND", "DRAM",
    "台积电", "中芯国际", "华虹", "寒武纪", "海光", "英伟达", "AMD", "ASML",
    # AI/科技
    "人工智能", "AI", "大模型", "算力", "数据中心", "CPO", "光模块",
    "Meta", "谷歌", "微软", "亚马逊", "苹果", "特斯拉",
    # 新能源
    "新能源", "光伏", "锂电", "电池", "固态电池", "钠离子", "储能", "充电桩",
    "碳酸锂", "宁德时代", "比亚迪", "赣锋", "阳光电源", "先导智能",
    # 油气/能源
    "石油", "原油", "天然气", "LNG", "布伦特", "OPEC",
    "中国海油", "中国石油", "中国石化",
    # 消费
    "消费", "白酒", "茅台", "五粮液", "家电", "汽车",
    # 医药
    "医药", "创新药", "CXO", "医疗器械", "百济神州",
    # 金融/地产
    "银行", "券商", "保险", "地产",
    # 港股
    "港股", "恒生", "腾讯", "阿里巴巴", "美团",
    # 周期
    "黄金", "铜", "铝", "钢铁", "煤炭", "化工",
]


def _extract_atomic_keywords(text: str) -> list[str]:
    """从文本中提取原子化产业关键词（去重保序）。"""
    if not text:
        return []
    found = []
    for kw in _ATOMIC_INDUSTRY_KEYWORDS:
        if kw in text:
            found.append(kw)
    return list(dict.fromkeys(found))


def extract_sector_keywords(news_list: list[Dict]) -> list[str]:
    """从新闻列表提取行业关键词，按频率排序返回前 20。"""
    all_kw = []
    for item in news_list:
        text = (item.get("title", "") or "") + " " + (item.get("content", "") or "")
        all_kw.extend(_extract_atomic_keywords(text))
    counter = Counter(all_kw)
    return [kw for kw, _ in counter.most_common(20)]


def extract_hot_sectors(news_results: List[Dict]) -> Dict[str, float]:
    """从多只基金的新闻分析结果中提取热点行业及热度得分。"""
    event_heat = Counter()
    all_news = []
    for nr in news_results or []:
        for event in nr.get("events", []) or []:
            weight = abs(float(event.get("impact_score", 0) or 0)) + float(event.get("decay_weight", 0) or 0) * 0.2
            for asset in event.get("affected_assets", [])[:5]:
                event_heat[asset] += weight
        for item in nr.get("news_list", []):
            all_news.append(item)

    sectors = extract_sector_keywords(all_news)
    sector_counts = Counter(sectors)
    sector_counts.update(event_heat)
    max_count = max(sector_counts.values()) if sector_counts else 1
    return {s: c / max_count for s, c in sector_counts.most_common(10)}


def screen_funds(
    hot_sectors: Dict[str, float],
    min_size: float = 1.0,
    top_pct: float = 0.20,
) -> List[Dict]:
    """全市场基金筛选：收益动量 + 申购状态。

    AKShare 的排行接口字段不稳定，所以这里尽量宽容处理字段名。
    """
    candidates = []

    try:
        import akshare as ak
        df = ak.fund_exchange_rank_em()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("基金代码", "")).zfill(6)
                name = str(row.get("基金简称", "") or row.get("基金名称", ""))
                if not code or code == "000nan" or not name:
                    continue
                ret_1m = _safe_float(row.get("近1月", row.get("近1月收益率", 0)))
                ret_3m = _safe_float(row.get("近3月", row.get("近3月收益率", 0)))
                ret_6m = _safe_float(row.get("近6月", row.get("近6月收益率", 0)))
                fund_type = str(row.get("类型", row.get("基金类型", "")))
                size = _safe_float(row.get("基金规模", row.get("最新规模", None)))

                if size is not None and size < min_size:
                    continue

                status = str(row.get("申购状态", "开放申购"))
                if "暂停" in status or "封闭" in status:
                    continue

                theme = infer_theme(name, fund_type)
                candidates.append({
                    "code": code,
                    "name": name,
                    "type": fund_type,
                    "return_1m": ret_1m,
                    "return_3m": ret_3m,
                    "return_6m": ret_6m,
                    "size": size,
                    "theme": theme,
                    "style_tags": infer_style_tags(name, fund_type),
                    "source": "akshare_rank",
                })
    except Exception:
        pass

    seen = set()
    unique = []
    for c in candidates:
        if c["code"] not in seen:
            seen.add(c["code"])
            unique.append(c)

    unique.sort(key=lambda x: x.get("return_1m", 0) or 0, reverse=True)
    limit = max(20, int(len(unique) * top_pct))
    return unique[:limit]


def build_holding_profiles(funds=None, holding_codes: Set[str] = None) -> List[Dict]:
    """从已加载的持仓基金数据 dict 中构造相似度画像。"""
    profiles = []
    if not funds:
        return profiles

    for code, fund in funds.items():
        if holding_codes and code not in holding_codes:
            continue
        basic = fund.get("basic", {}) or {}
        name = basic.get("name", code)
        fund_type = basic.get("fund_type", "")
        perf_1y = (fund.get("perf", {}) or {}).get("近1年", {}) or {}
        perf_3y = (fund.get("perf", {}) or {}).get("近3年", {}) or {}
        profiles.append({
            "code": code,
            "name": name,
            "type": fund_type,
            "theme": infer_theme(name, fund_type),
            "style_tags": infer_style_tags(name, fund_type),
            "return_1m": None,
            "return_3m": None,
            "return_6m": None,
            "annual_volatility": _safe_float(perf_1y.get("annual_volatility")),
            "max_drawdown": _safe_float(perf_3y.get("max_drawdown")),
            "sharpe": _safe_float(perf_1y.get("sharpe_ratio")),
        })
    return profiles


def filter_by_correlation(
    candidates: List[Dict],
    holding_codes: Set[str],
    holding_profiles: List[Dict] = None,
    max_similarity: float = 0.92,
) -> List[Dict]:
    """兼容旧名称：排除已持仓，并为候选补充多维相似度。

    不再简单按相关性硬过滤，因为高相似候选也可能有收益机会；相似度会进入排序和理由。
    只有接近重复暴露的候选（max_similarity >= max_similarity）才剔除。
    """
    filtered = []
    holding_profiles = holding_profiles or []
    for c in candidates:
        code = c["code"]
        if code in holding_codes:
            continue
        enriched = _attach_similarity(c, holding_profiles)
        if enriched.get("max_similarity", 0) >= max_similarity:
            continue
        filtered.append(enriched)
    return filtered


def rank_recommendations(
    candidates: List[Dict],
    hot_sectors: Dict[str, float],
    top_n: int = 5,
    max_theme_ratio: float = 0.35,
) -> List[Dict]:
    """综合排序：机会 + 热点 + 分散度 + 稳健性，并控制同质化。"""
    if not candidates:
        return []

    momentum_values = [_momentum_value(c) for c in candidates]
    max_abs_momentum = max(abs(v) for v in momentum_values) or 1.0

    ranked = []
    for c, momentum in zip(candidates, momentum_values):
        heat = _theme_heat(c, hot_sectors)
        momentum_score = max(0.0, min(1.0, momentum / max_abs_momentum))
        diversification = max(0.0, 1.0 - c.get("max_similarity", 0))
        stability = _stability_score(c)
        cluster = infer_exposure_cluster(c)
        crowded_growth_penalty = 0.08 if cluster == "growth_manufacturing" and c.get("max_similarity", 0) > 0.45 else 0
        score = (
            momentum_score * 0.32
            + heat * 0.15
            + diversification * 0.38
            + stability * 0.15
            - crowded_growth_penalty
        )
        ranked.append({
            **c,
            "exposure_cluster": cluster,
            "portfolio_role": _portfolio_role(cluster),
            "heat_score": round(heat, 4),
            "momentum_score": round(momentum_score, 4),
            "diversification_score": round(diversification, 4),
            "marginal_benefit": round(diversification * 0.65 + stability * 0.20 + heat * 0.15, 4),
            "score": round(score, 4),
        })

    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    return _apply_diversity_constraint(ranked, top_n, max_theme_ratio)


def rank_recommendations_with_portfolio(
    candidates: List[Dict],
    hot_sectors: Dict[str, float],
    portfolio_risk: Dict = None,
    top_n: int = 5,
    max_theme_ratio: float = 0.35,
) -> List[Dict]:
    """Rank candidates with portfolio exposure gaps and crowding penalties."""
    ranked = rank_recommendations(
        candidates,
        hot_sectors,
        top_n=max(len(candidates), top_n),
        max_theme_ratio=1.0,
    )
    if not ranked:
        return []

    exposures = (portfolio_risk or {}).get("cluster_exposures") or {}
    adjusted = []
    for rec in ranked:
        cluster = rec.get("exposure_cluster") or infer_exposure_cluster(rec)
        exposure = float(exposures.get(cluster, 0.0) or 0.0)
        portfolio_adjustment = 0.0
        risk_budget_impact = "neutral"

        if cluster == "defensive_income" and exposure < 0.10:
            portfolio_adjustment += 0.35
            risk_budget_impact = "补足防守资产，降低组合波动"
        elif cluster in ("value_dividend", "commodity", "overseas") and exposure < 0.08:
            portfolio_adjustment += 0.12
            risk_budget_impact = "补足低相关暴露"

        if cluster == "growth_manufacturing" and exposures.get("growth_manufacturing", 0.0) > 0.50:
            portfolio_adjustment -= 0.25
            risk_budget_impact = "成长制造已拥挤，新增会提高回撤风险"
        elif exposure > 0.35:
            portfolio_adjustment -= 0.10
            risk_budget_impact = "同类暴露偏高，适合替代观察"

        adjusted_score = round(float(rec.get("score", 0) or 0) + portfolio_adjustment, 4)
        adjusted.append({
            **rec,
            "score": adjusted_score,
            "portfolio_adjustment": round(portfolio_adjustment, 4),
            "risk_budget_impact": risk_budget_impact,
            "entry_plan": _entry_plan(rec, cluster, portfolio_adjustment),
        })

    adjusted.sort(key=lambda x: x.get("score", 0), reverse=True)
    constrained = _apply_diversity_constraint(adjusted, top_n, max_theme_ratio)
    return constrained[:top_n]


def compute_inter_recommendation_correlations(
    recommendations: List[Dict],
) -> Dict:
    """计算推荐基金之间的两两相似度矩阵。

    返回:
        dict with:
            "matrix": List[List[float]] — 两两相似度矩阵
            "labels": List[str] — 代码标签
            "warnings": List[str] — 高度相关 (>0.85) 的配对警告
    """
    n = len(recommendations)
    labels = [r.get("code", str(i)) for i, r in enumerate(recommendations)]
    matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    warnings = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = compute_fund_similarity(recommendations[i], recommendations[j])
            matrix[i][j] = sim["composite"]
            matrix[j][i] = sim["composite"]
            if sim["composite"] > 0.85:
                warnings.append(
                    f"⚠️ {labels[i]} {recommendations[i].get('name','')} ↔ "
                    f"{labels[j]} {recommendations[j].get('name','')} "
                    f"相似度 {sim['composite']:.2f}，推荐组合内高度相关，建议只选其一"
                )
    return {"matrix": matrix, "labels": labels, "warnings": warnings}


def generate_recommendation_reasons(
    recommendations: List[Dict],
) -> List[Dict]:
    """为推荐基金生成推荐理由，并用 Pydantic 校验输出结构。

    最终推荐取舍由接入 skill 的 agent 完成；这里负责生成稳定的候选理由。
    """
    validated = []
    for rec in recommendations:
        ret_1m = rec.get("return_1m", 0) or 0
        theme = rec.get("theme", "其他")
        reasons = []
        if ret_1m > 0:
            reasons.append(f"近1月收益{ret_1m:+.1f}%，短期动量较强")
        if rec.get("heat_score", 0) >= 0.5:
            reasons.append(f"{theme}主题近期新闻热度较高")
        if rec.get("max_similarity", 0) < 0.45:
            reasons.append("与现有持仓相似度低，有助于分散组合")
        elif rec.get("max_similarity", 0) < 0.75:
            reasons.append("与现有持仓中等相似，需控制同主题仓位")
        else:
            reasons.append("与现有持仓相似度偏高，仅适合作为替代观察")
        if rec.get("diversification_score", 0) >= 0.6:
            reasons.append("分散度评分较好")
        if rec.get("portfolio_role"):
            reasons.append(f"组合角色：{rec.get('portfolio_role')}")

        rec["reason"] = "；".join(reasons) if reasons else "综合因子得分较高"
        rec["risks"] = _candidate_risks(rec)
        model = RecommendationCandidate.model_validate(rec)
        validated.append(model.model_dump())

    return validated


def compute_fund_similarity(target_fund: Dict, candidate_fund: Dict) -> Dict:
    """计算候选基金与某只持仓基金的多维相似度。"""
    sector_sim = sector_overlap(target_fund, candidate_fund)
    style_sim = style_similarity(target_fund, candidate_fund)
    return_sim = return_risk_similarity(target_fund, candidate_fund)
    composite = 0.40 * sector_sim + 0.25 * style_sim + 0.35 * return_sim
    return {
        "composite": round(composite, 4),
        "sector": round(sector_sim, 4),
        "style": round(style_sim, 4),
        "return_risk": round(return_sim, 4),
    }


def sector_overlap(target_fund: Dict, candidate_fund: Dict) -> float:
    target = {target_fund.get("theme") or infer_theme(target_fund.get("name", ""), target_fund.get("type", ""))}
    candidate = {candidate_fund.get("theme") or infer_theme(candidate_fund.get("name", ""), candidate_fund.get("type", ""))}
    if "其他" in target:
        target |= set(infer_style_tags(target_fund.get("name", ""), target_fund.get("type", "")))
    if "其他" in candidate:
        candidate |= set(infer_style_tags(candidate_fund.get("name", ""), candidate_fund.get("type", "")))
    return _jaccard(target, candidate)


def style_similarity(target_fund: Dict, candidate_fund: Dict) -> float:
    target = set(target_fund.get("style_tags") or infer_style_tags(target_fund.get("name", ""), target_fund.get("type", "")))
    candidate = set(candidate_fund.get("style_tags") or infer_style_tags(candidate_fund.get("name", ""), candidate_fund.get("type", "")))
    return _jaccard(target, candidate)


def return_risk_similarity(target_fund: Dict, candidate_fund: Dict) -> float:
    sims = []
    for key, scale in [
        ("return_1m", 20.0),
        ("return_3m", 35.0),
        ("return_6m", 50.0),
        ("annual_volatility", 40.0),
        ("max_drawdown", 50.0),
    ]:
        a = _safe_float(target_fund.get(key))
        b = _safe_float(candidate_fund.get(key))
        if a is None or b is None:
            continue
        sims.append(max(0.0, 1.0 - abs(a - b) / scale))
    return sum(sims) / len(sims) if sims else 0.35


def infer_theme(name: str, fund_type: str = "") -> str:
    text = f"{name or ''} {fund_type or ''}"
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return theme
    return "其他"


def infer_style_tags(name: str, fund_type: str = "") -> List[str]:
    text = f"{name or ''} {fund_type or ''}"
    tags = [tag for tag, keywords in STYLE_KEYWORDS.items() if any(kw in text for kw in keywords)]
    if "QDII" in text and "overseas" not in tags:
        tags.append("overseas")
    return tags or ["balanced"]


def infer_exposure_cluster(candidate: Dict) -> str:
    """更粗粒度的暴露簇，用于防止推荐全挤在半导体/新能源/电池链条。"""
    text = f"{candidate.get('name', '')} {candidate.get('type', '')} {candidate.get('theme', '')}"
    if any(kw in text for kw in ["债", "固收", "货币", "短债"]):
        return "defensive_income"
    if any(kw in text for kw in ["红利", "价值", "银行", "低波", "股息"]):
        return "value_dividend"
    if any(kw in text for kw in ["QDII", "纳斯达克", "标普", "海外", "全球", "新兴市场"]):
        return "overseas"
    if any(kw in text for kw in ["医药", "医疗", "创新药", "生物"]):
        return "healthcare"
    if any(kw in text for kw in ["半导体", "芯片", "新能源", "电池", "光伏", "储能", "AI", "人工智能", "科技"]):
        return "growth_manufacturing"
    if any(kw in text for kw in ["黄金", "石油", "原油", "商品", "能源"]):
        return "commodity"
    if any(kw in text for kw in ["沪深300", "中证500", "中证1000", "上证50", "宽基"]):
        return "broad_beta"
    return "balanced_other"


def _portfolio_role(cluster: str) -> str:
    return {
        "defensive_income": "防守现金流/降低波动",
        "value_dividend": "红利价值/低波补充",
        "overseas": "海外资产/币种分散",
        "commodity": "商品或通胀对冲",
        "healthcare": "医药消费防守成长",
        "growth_manufacturing": "成长制造进攻仓位",
        "broad_beta": "宽基底仓",
        "balanced_other": "均衡补充",
    }.get(cluster, "均衡补充")


def _candidate_risks(candidate: Dict) -> List[str]:
    cluster = candidate.get("exposure_cluster") or infer_exposure_cluster(candidate)
    risks = {
        "defensive_income": ["利率上行", "信用利差扩大"],
        "value_dividend": ["高股息拥挤", "经济修复低于预期"],
        "overseas": ["海外估值回撤", "汇率波动"],
        "commodity": ["商品价格反转", "地缘事件降温"],
        "healthcare": ["政策监管", "研发或集采不确定性"],
        "growth_manufacturing": ["估值收缩", "交易拥挤", "业绩兑现压力"],
        "broad_beta": ["市场系统性回撤"],
    }
    return risks.get(cluster, ["风格轮动风险"])


def _entry_plan(candidate: Dict, cluster: str, portfolio_adjustment: float) -> str:
    if cluster == "defensive_income" and portfolio_adjustment > 0:
        return "分批买入"
    if candidate.get("max_similarity", 0) >= 0.65:
        return "替代观察"
    if cluster == "growth_manufacturing":
        return "回调小额试仓"
    return "分批建仓"


def _attach_similarity(candidate: Dict, holding_profiles: List[Dict]) -> Dict:
    if not holding_profiles:
        return {
            **candidate,
            "avg_similarity": 0.0,
            "max_similarity": 0.0,
            "sector_similarity": 0.0,
            "style_similarity": 0.0,
            "return_similarity": 0.0,
        }

    sims = [compute_fund_similarity(h, candidate) for h in holding_profiles]
    return {
        **candidate,
        "avg_similarity": round(sum(s["composite"] for s in sims) / len(sims), 4),
        "max_similarity": max(s["composite"] for s in sims),
        "sector_similarity": round(sum(s["sector"] for s in sims) / len(sims), 4),
        "style_similarity": round(sum(s["style"] for s in sims) / len(sims), 4),
        "return_similarity": round(sum(s["return_risk"] for s in sims) / len(sims), 4),
    }


def _apply_diversity_constraint(candidates: List[Dict], top_n: int, max_theme_ratio: float) -> List[Dict]:
    max_per_theme = max(1, ceil(top_n * max_theme_ratio))
    max_per_cluster = max(1, ceil(top_n * 0.35))
    selected = []
    theme_counts = Counter()
    cluster_counts = Counter()
    deferred = []

    for c in candidates:
        theme = c.get("theme", "其他")
        cluster = c.get("exposure_cluster") or infer_exposure_cluster(c)
        if theme_counts[theme] < max_per_theme and cluster_counts[cluster] < max_per_cluster:
            selected.append(c)
            theme_counts[theme] += 1
            cluster_counts[cluster] += 1
        else:
            deferred.append(c)
        if len(selected) >= top_n:
            return selected

    # 若候选不足，先用未超主题上限的候选补位，再逐步放宽约束。
    deferred.sort(key=lambda c: theme_counts[c.get("theme", "其他")] >= max_per_theme)
    for c in deferred:
        theme = c.get("theme", "其他")
        if theme_counts[theme] >= max_per_theme and any(
            theme_counts[item.get("theme", "其他")] < max_per_theme
            for item in deferred
            if item is not c
        ):
            continue
        cluster = c.get("exposure_cluster") or infer_exposure_cluster(c)
        if len(selected) >= max(2, top_n // 2) and cluster_counts[cluster] >= max_per_cluster + 1:
            continue
        selected.append(c)
        theme_counts[theme] += 1
        cluster_counts[cluster] += 1
        if len(selected) >= top_n:
            break
    return selected


def _momentum_value(candidate: Dict) -> float:
    return (
        (_safe_float(candidate.get("return_1m")) or 0) * 0.5
        + (_safe_float(candidate.get("return_3m")) or 0) * 0.3
        + (_safe_float(candidate.get("return_6m")) or 0) * 0.2
    )


def _theme_heat(candidate: Dict, hot_sectors: Dict[str, float]) -> float:
    name = candidate.get("name", "")
    theme = candidate.get("theme", "")
    direct = max((score for sector, score in hot_sectors.items() if sector in name), default=0.0)
    theme_match = max((score for sector, score in hot_sectors.items() if sector in theme), default=0.0)
    return max(direct, theme_match, 0.2 if hot_sectors else 0.1)


def _stability_score(candidate: Dict) -> float:
    ret_1m = _safe_float(candidate.get("return_1m")) or 0
    ret_3m = _safe_float(candidate.get("return_3m")) or 0
    ret_6m = _safe_float(candidate.get("return_6m")) or 0
    if ret_1m >= 0 and ret_3m >= 0 and ret_6m >= 0:
        return 1.0
    if ret_3m >= 0 and ret_6m >= 0:
        return 0.7
    if ret_6m >= 0:
        return 0.5
    return 0.2


def _jaccard(a: Set[str], b: Set[str]) -> float:
    a = {x for x in a if x}
    b = {x for x in b if x}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace("%", "").replace(",", ""))
    except (ValueError, TypeError):
        return None
