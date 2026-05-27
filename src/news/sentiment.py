"""
舆情动力学与指数衰减聚合模块

剔除 SnowNLP，改用结构化金融行业情感特征极性字典。
每条新闻转换为 Severity（[-1.0, +1.0]）和 Impact（[0.0, 1.0]）的连续值。
日频聚合后执行指数时间衰减加权归一。
"""

import numpy as np
from collections import Counter
from typing import List, Dict
from src.config.defaults import QUANT_CONFIG


# ============================================================
# 金融情感极性字典
# ============================================================

_FINANCE_POSITIVE_WORDS = {
    # 行情与技术面
    "暴涨", "飙升", "利好", "突破", "创新高", "超预期", "放量", "主升浪",
    "涨停", "龙头", "领涨", "强劲", "反弹", "反转", "企稳回升",
    # 资金面
    "回购", "增持", "买入", "加仓", "净流入", "主力净流入", "资金流入",
    "北向资金", "南向资金",
    # 基本面
    "盈利增长", "营收增长", "分红", "业绩翻倍", "订单增长", "需求旺盛",
    "产能扩张", "毛利率提升", "扭亏为盈",
    # 产业/政策
    "政策支持", "补贴", "国产替代", "自主可控", "技术突破", "先发优势",
    "合作", "新订单", "获批", "上市", "IPO",
    # AI/科技
    "AI", "人工智能", "大模型", "算力", "数据中心", "英伟达", "台积电",
    "HBM", "CoWoS", "CPO", "光模块", "光刻机",
    # 新能源
    "固态电池", "钠离子", "储能", "充电桩", "宁德时代",
}

_FINANCE_NEGATIVE_WORDS = {
    # 行情与技术面
    "暴跌", "崩盘", "利空", "破位", "创新低", "不及预期", "缩量", "阴跌",
    "跌停", "踩踏", "恐慌", "跳水", "下挫",
    # 资金面
    "减持", "卖出", "减仓", "净流出", "主力净流出", "资金出逃",
    # 基本面
    "亏损", "下滑", "萎缩", "裁员", "毛利率下降", "债务违约", "爆雷",
    "退市", "ST", "停牌", "业绩变脸", "商誉减值",
    # 产业/政策
    "贸易战", "制裁", "管制", "出口管制", "加息", "收紧", "通胀", "衰退",
    "诉讼", "处罚", "警告", "违规", "调查", "产能过剩", "价格战",
    # 风险事件
    "战争", "冲突", "关闭", "中断", "封锁",
}


# ============================================================
# 原子化产业关键词白名单（精确匹配）
# ============================================================

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


# ============================================================
# 核心计算函数
# ============================================================

def _compute_sentiment_severity(text: str) -> float:
    """基于金融极性词典计算文本情绪强度 Severity ∈ [-1.0, +1.0]
    
    正面词数 - 负面词数，除以总命中词数，映射到 [-1, 1]。
    未命中任何极性词 → 0.0（中性）。
    """
    if not text:
        return 0.0
    
    pos_count = sum(1 for w in _FINANCE_POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in _FINANCE_NEGATIVE_WORDS if w in text)
    
    total = pos_count + neg_count
    if total == 0:
        return 0.0
    
    severity = (pos_count - neg_count) / total
    return round(severity, 4)


def _compute_news_impact(news_item: dict, holding_keywords: list = None) -> float:
    """计算单条新闻的产业链直接冲击权重 Impact ∈ [0.0, 1.0]
    
    匹配重仓股关键词权重最高，公司公告次之，普通电报最低。
    """
    base_impact = 0.3
    
    # 检查是否匹配重仓股关键词
    if holding_keywords:
        title = news_item.get("title", "") or ""
        content = news_item.get("content", "") or ""
        combined = title + " " + content
        matches = sum(1 for kw in holding_keywords if kw in combined)
        if matches > 0:
            base_impact = min(1.0, 0.3 + 0.15 * matches)
    
    # 来源权重提权
    source = news_item.get("source", "") or ""
    if "公告" in source or "财报" in source:
        base_impact = max(base_impact, 1.0)
    elif "要闻" in source:
        base_impact = max(base_impact, 0.5)
    
    return round(base_impact, 2)


def _extract_atomic_keywords(text: str) -> List[str]:
    """从文本中提取原子化产业关键词（白名单精确匹配）
    
    返回无空格、无泛化词的原子名词列表，去重保序。
    """
    if not text:
        return []
    
    found = []
    for kw in _ATOMIC_INDUSTRY_KEYWORDS:
        if kw in text:
            found.append(kw)
    
    return list(dict.fromkeys(found))  # 去重保序


# ============================================================
# 公开 API（兼容旧接口签名）
# ============================================================

def analyze_sentiment(
    news_list: List[Dict],
    holding_keywords: list = None
) -> List[Dict]:
    """对新闻列表进行情感分析（基于金融极性词典）
    
    每项添加: sentiment_score, sentiment_label, severity, impact, keywords
    不再依赖 SnowNLP。
    """
    enriched = []
    for item in news_list:
        text = (item.get("title", "") or "") + " " + (item.get("content", "") or "")
        
        # 计算 Severity（-1 到 +1）
        severity = _compute_sentiment_severity(text)
        
        # 计算 Impact（0 到 1）
        impact = _compute_news_impact(item, holding_keywords)
        
        # 综合分数 = severity * impact，再映射回 [0, 1] 兼容区间
        raw_score = severity * impact
        sentiment_score = round((raw_score + 1.0) / 2.0, 4)
        
        # 标签
        if severity > 0.2:
            label = "positive"
        elif severity < -0.2:
            label = "negative"
        else:
            label = "neutral"
        
        enriched.append({
            **item,
            "sentiment_score": sentiment_score,
            "sentiment_label": label,
            "severity": severity,
            "impact": impact,
            "keywords": _extract_atomic_keywords(text),
        })
    
    return enriched


def daily_sentiment_aggregate(
    news_with_sentiment: List[Dict],
    lam: float = None
) -> List[Dict]:
    """按日聚合情绪，并执行指数时间衰减加权归一
    
    Args:
        news_with_sentiment: analyze_sentiment 的输出列表
        lam: 时间衰减系数 λ。默认从 QUANT_CONFIG.NEWS_LAMBDA 读取。
    
    Returns:
        按日期排序的聚合列表，末项含 decayed_sentiment_final 终值
    """
    if lam is None:
        lam = QUANT_CONFIG.get("NEWS_LAMBDA", 0.200)
    
    # 第一步：按日期分组
    by_date = {}
    for item in news_with_sentiment:
        date_key = item.get("date", "") or item.get("publish_date", "")
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(item)
    
    # 第二步：逐日统计
    daily_aggs = []
    for date_key in sorted(by_date.keys()):
        items = by_date[date_key]
        n = len(items)
        
        # 使用 severity * impact 的原始极性（-1~+1）计算均值
        raw_polarities = [
            it.get("severity", 0.0) * it.get("impact", 0.3)
            for it in items
        ]
        polarity_mean = float(np.mean(raw_polarities)) if raw_polarities else 0.0
        
        # 映射回 [0, 1] 兼容旧接口
        sentiment_mean_01 = round((polarity_mean + 1.0) / 2.0, 4)
        
        labels = [it.get("sentiment_label", "neutral") for it in items]
        pos_count = labels.count("positive")
        neg_count = labels.count("negative")
        
        # 关键词聚合
        all_kw = []
        for it in items:
            all_kw.extend(it.get("keywords", []))
        kw_counter = Counter(all_kw)
        
        daily_aggs.append({
            "date": str(date_key),
            "positive_rate": round(pos_count / n, 4) if n else 0,
            "negative_rate": round(neg_count / n, 4) if n else 0,
            "neutral_rate": round((n - pos_count - neg_count) / n, 4) if n else 0,
            "sentiment_mean": sentiment_mean_01,
            "news_count": n,
            "top_keywords": [kw for kw, _ in kw_counter.most_common(10)],
        })
    
    # 第三步：全局时间衰减加权终值
    if daily_aggs:
        total_weight = 0.0
        weighted_sum = 0.0
        current_idx = len(daily_aggs) - 1
        
        for idx, agg in enumerate(daily_aggs):
            delta_t = current_idx - idx
            decay_weight = np.exp(-lam * delta_t)
            weighted_sum += agg["sentiment_mean"] * decay_weight
            total_weight += decay_weight
        
        decayed_final = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.5
        
        daily_aggs[-1]["decayed_sentiment_final"] = decayed_final
    
    return daily_aggs


def extract_sector_keywords(news_list: List[Dict]) -> List[str]:
    """从新闻列表提取行业关键词（兼容旧接口）
    
    使用原子化白名单匹配，按频率排序返回前 20。
    """
    all_kw = []
    for item in news_list:
        text = (item.get("title", "") or "") + " " + (item.get("content", "") or "")
        all_kw.extend(_extract_atomic_keywords(text))
    
    counter = Counter(all_kw)
    return [kw for kw, _ in counter.most_common(20)]
