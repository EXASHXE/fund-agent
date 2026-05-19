"""AKShare 新闻采集 — 按基金重仓股票和关键词获取相关新闻"""
from datetime import date, timedelta
from src.config.shared import today as _shared_today
from typing import List, Dict, Tuple
import hashlib
import re


def extract_holding_keywords(fund_code: str, limit: int = 10) -> Tuple[List[str], List[str]]:
    """从基金最新重仓中提取股票代码和名称关键词。"""
    stock_codes = []
    keywords = []
    holding_rows = []
    for year in ["2025", "2024"]:
        try:
            import akshare as ak
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    code = str(row.get("股票代码", "")).strip()
                    if re.fullmatch(r"\d{6}", code):
                        stock_codes.append(code)
                    name = _normalize_company_name(str(row.get("股票名称", "")))
                    weight = _pick_first(row, ["占净值比例", "持仓占比", "占比", "持股占比"])
                    holding_rows.append({
                        "stock_code": code,
                        "stock_name": name,
                        "weight": weight,
                    })
                    if name and len(name) >= 2:
                        keywords.append(name)
                break  # 使用最新可用的数据
        except Exception:
            continue

    # 去重且限制数量，优先保留前 limit 个（按持仓权重排序）
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return stock_codes[:limit], result[:8]


def build_news_search_profile(
    fund_code: str,
    fund_name: str,
    fund_type: str = "",
    agent_keywords: List[str] = None,
    limit: int = 10,
) -> Dict:
    """构造新闻搜索画像。

    代码只提供真实重仓、基金名和少量兜底词；行业链条和扩展关键词应由
    接入 skill 的 agent 基于这些证据自主判断后通过 keywords 传入。
    """
    if agent_keywords:
        stock_codes, stock_keywords = [], []
    else:
        stock_codes, stock_keywords = extract_holding_keywords(fund_code, limit=limit)
    profile = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "stock_codes": stock_codes,
        "holding_keywords": stock_keywords,
        "agent_keywords": agent_keywords or [],
        "fallback_keywords": _fallback_fund_keywords(fund_name, fund_type),
    }
    terms = []
    for group in ["holding_keywords", "agent_keywords", "fallback_keywords"]:
        for kw in profile[group]:
            if kw and kw not in terms:
                terms.append(kw)
    if fund_code not in terms:
        terms.append(fund_code)
    profile["search_terms"] = terms
    return profile


def fetch_fund_news(
    fund_code: str,
    fund_name: str,
    keywords: List[str] = None,
    days: int = 7,
    fund_type: str = "",
) -> List[Dict]:
    """获取与基金相关的近期新闻。优先按重仓股票搜索，次选基金名称/代码。"""
    try:
        import akshare as ak
    except ImportError:
        return []

    all_news = []
    seen = set()

    profile = build_news_search_profile(
        fund_code=fund_code,
        fund_name=fund_name,
        fund_type=fund_type,
        agent_keywords=keywords,
    )
    search_terms = profile["search_terms"]
    stock_codes = profile["stock_codes"]

    cutoff = _shared_today() - timedelta(days=days)

    # 个股新闻接口只适合股票代码，不适合中文关键词。
    for code in stock_codes:
        try:
            df = ak.stock_news_em(symbol=code)
            _append_news_from_df(all_news, seen, df, cutoff, source_hint=f"东方财富个股新闻:{code}")
        except Exception:
            continue

    # 全市场新闻兜底：先抓通用新闻，再用基金/行业/持仓关键词本地过滤。
    market_frames = list(_fetch_market_news_frames(ak, days))
    for df, source_hint in market_frames:
        _append_news_from_df(
            all_news,
            seen,
            df,
            cutoff,
            source_hint=source_hint,
            include_terms=search_terms,
        )

    # 降级匹配：首轮关键词无命中时，缩短关键词复用已缓存帧重试
    if not all_news:
        degraded_terms = _degrade_keywords(search_terms)
        if degraded_terms and degraded_terms != search_terms:
            for df, source_hint in market_frames:
                _append_news_from_df(
                    all_news, seen, df, cutoff,
                    source_hint=source_hint,
                    include_terms=degraded_terms,
                )

    all_news.sort(key=lambda x: x.get("date", ""), reverse=True)
    return all_news


def _fetch_market_news_frames(ak, days: int):
    frames = []

    # 财联社电报全量流（时效性更强、数据量更大）
    try:
        frames.append((ak.stock_telegraph_cls(), "财联社电报全量"))
    except Exception:
        pass

    # 财联社分类电报
    for symbol in ["全部", "重点"]:
        try:
            frames.append((ak.stock_info_global_cls(symbol=symbol), f"财联社电报:{symbol}"))
        except Exception:
            pass

    # 行业新闻兜底（申万一级行业覆盖）
    for industry in ["半导体", "新能源", "医药", "消费", "科技"]:
        try:
            frames.append((ak.stock_info_global_cls(symbol=industry), f"行业新闻:{industry}"))
        except Exception:
            pass

    try:
        frames.append((ak.stock_news_main_cx(), "财新数据通"))
    except Exception:
        pass

    # 新闻联播（最多回看 3 天）
    for i in range(min(days, 3)):
        d = (_shared_today() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            frames.append((ak.news_cctv(date=d), f"新闻联播:{d}"))
        except Exception:
            pass

    return frames


def _append_news_from_df(
    all_news: List[Dict],
    seen: set,
    df,
    cutoff: date,
    source_hint: str = "",
    include_terms: List[str] = None,
):
    if df is None or getattr(df, "empty", True):
        return

    for _, row in df.iterrows():
        title = _pick_first(row, ["新闻标题", "标题", "title", "内容标题", "事件标题"])
        content = _pick_first(row, ["新闻内容", "内容", "摘要", "summary", "事件内容", "详情"])
        date_raw = _pick_first(row, ["发布时间", "发布日期", "时间", "日期", "date", "datetime"])
        source = _pick_first(row, ["文章来源", "来源", "source"]) or source_hint
        url = _pick_first(row, ["新闻链接", "链接", "url", "网址"])

        text = f"{title} {content}".strip()
        if not title and not content:
            continue
        if include_terms and not _matches_terms(text, include_terms):
            continue

        news_date = _parse_date(date_raw)
        if news_date and news_date < cutoff:
            continue

        digest = hashlib.md5(f"{title}|{source}|{url}".encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)

        all_news.append({
            "title": title or content[:80],
            "content": content[:500],
            "date": news_date.isoformat() if news_date else "",
            "source": source,
            "url": url,
        })


def _pick_first(row, names: List[str]) -> str:
    for name in names:
        if name in row and row.get(name) is not None:
            value = str(row.get(name)).strip()
            if value and value.lower() != "nan":
                return value
    return ""


def _matches_terms(text: str, terms: List[str]) -> bool:
    """中英文统一子串匹配。"""
    if not text:
        return False
    text_lower = text.lower()
    for term in terms:
        term = str(term).strip()
        if len(term) < 2:
            continue
        if term.lower() in text_lower:
            return True
    return False


def _degrade_keywords(terms: List[str]) -> List[str]:
    """关键词降级：截取前3字用于二次扫描。"""
    degraded = []
    for t in terms:
        t = str(t).strip()
        if len(t) >= 3:
            degraded.append(t[:3])
        elif len(t) == 2:
            degraded.append(t)
    seen = set()
    result = []
    for kw in degraded:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _fallback_fund_keywords(fund_name: str, fund_type: str = "") -> List[str]:
    text = f"{fund_name or ''} {fund_type or ''}"
    terms = []
    core_name = (fund_name or "").split("(")[0].split("（")[0].strip()
    if core_name:
        terms.append(core_name)
    if "QDII" in text or "qdii" in text.lower():
        terms.extend(["海外市场", "汇率"])
    for literal in ["纳斯达克", "标普", "恒生", "黄金", "石油", "半导体", "新能源", "医药", "消费"]:
        if literal in text:
            terms.append(literal)
    if "债" in text:
        terms.extend(["利率", "信用债"])
    if "指数" in text or "ETF" in text:
        terms.append("指数")
    return terms


def _normalize_company_name(name: str) -> str:
    if "(" in name:
        name = name.split("(")[0].strip()
    if "（" in name:
        name = name.split("（")[0].strip()
    for suffix in ["-A", "-B", "-C", "-W", " Inc", " Co", " Ltd", " Holdings"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name


def _parse_date(date_str: str) -> date:
    """解析多种日期格式"""
    if not date_str:
        return None
    if hasattr(date_str, "date"):
        try:
            return date_str.date()
        except Exception:
            pass
    raw = str(date_str).strip()
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            from datetime import datetime
            if "%H" in fmt:
                return datetime.strptime(raw[:19], fmt).date()
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None
