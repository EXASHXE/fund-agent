"""新闻去重模块 —— 标题级 + 语义级 + 事件级三层去重"""
import re
import hashlib
from typing import List, Dict, Set
from collections import defaultdict


def normalize_title(title: str) -> str:
    """标题归一化：去空格、去标点、统一小写。"""
    if not title:
        return ""
    t = title.strip()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[，,。\.！!？?\s\"\"''「」『』【】\[\]{}()（）《》]", "", t)
    return t.lower()


def exact_dedup(news_list: List[Dict], seen: Set[str] = None) -> List[Dict]:
    """标题级精确去重。

    新加入的新闻如果标题 hash 已存在于 seen，则丢弃。
    返回去重后的列表，seen 会被原地更新。
    """
    if seen is None:
        seen = set()
    result = []
    for item in news_list:
        title = normalize_title(item.get("title", ""))
        key = hashlib.md5(title.encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def semantic_dedup(
    news_list: List[Dict],
    threshold: float = 0.85,
) -> List[Dict]:
    """语义级去重 —— 基于标题 Jaccard 相似度。

    对于语义高度相似的标题（如不同来源报道同一事件），
    保留第一条，丢弃后续相似的。
    """
    if len(news_list) <= 1:
        return news_list

    texts = [normalize_title(item.get("title", "")) for item in news_list]
    keep = [True] * len(news_list)

    for i in range(len(texts)):
        if not keep[i]:
            continue
        words_i = set(texts[i])
        if not words_i:
            continue
        for j in range(i + 1, len(texts)):
            if not keep[j]:
                continue
            words_j = set(texts[j])
            if not words_j:
                continue
            intersection = words_i & words_j
            union = words_i | words_j
            sim = len(intersection) / len(union) if union else 0
            if sim >= threshold:
                keep[j] = False

    return [item for item, kept in zip(news_list, keep) if kept]


def event_level_dedup(
    news_list: List[Dict],
    time_window_hours: int = 6,
) -> List[Dict]:
    """事件级去重 —— 同一天、同实体、时间窗口内的新闻归并。

    在 time_window_hours 内，同一实体的多条新闻视为同一事件，
    保留最早的一条。
    """
    if len(news_list) <= 1:
        return news_list

    # 按发布时间分组
    grouped = defaultdict(list)
    for item in news_list:
        title = item.get("title", "")
        date_key = item.get("date", "") or item.get("publish_date", "") or ""
        entity_hits = item.get("entity_hits", []) or item.get("matched_terms", [])
        if entity_hits:
            key = (date_key, tuple(sorted(entity_hits[:3])))
        else:
            # No known shared entity: do not collapse unrelated same-day headlines.
            key = (date_key, normalize_title(title))
        grouped[key].append(item)

    result = []
    for items in grouped.values():
        result.append(items[0])  # 保留最早一条
    return result
