"""AKShare 新闻采集 — 按基金重仓股票和关键词获取相关新闻"""
from datetime import date, timedelta
from src.config.shared import today as _shared_today
from typing import List, Dict, Tuple
import hashlib
import re


def extract_holding_keywords(fund_code: str, limit: int = 10) -> Tuple[List[str], List[str]]:
    """从基金持仓中提取股票代码和名称关键词。"""
    stock_codes = []
    keywords = []
    for year in ["2025", "2024"]:
        try:
            import akshare as ak
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    code = str(row.get("股票代码", "")).strip()
                    if re.fullmatch(r"\d{6}", code):
                        stock_codes.append(code)
                    name = str(row.get("股票名称", ""))
                    # 提取核心名称：去掉括号中的代码、去掉后缀
                    if "(" in name:
                        name = name.split("(")[0].strip()
                    if "（" in name:
                        name = name.split("（")[0].strip()
                    # 去掉常见后缀
                    for suffix in ["-A", "-B", "-C", "-W", " Inc", " Co", " Ltd", " Holdings"]:
                        if name.endswith(suffix):
                            name = name[:-len(suffix)].strip()
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


def fetch_fund_news(
    fund_code: str,
    fund_name: str,
    keywords: List[str] = None,
    days: int = 7,
) -> List[Dict]:
    """获取与基金相关的近期新闻。优先按重仓股票搜索，次选基金名称/代码。"""
    try:
        import akshare as ak
    except ImportError:
        return []

    all_news = []
    seen = set()

    # 构建搜索词：优先持仓股票 > 用户提供的关键词 > 基金简称
    search_terms = []
    stock_codes = []

    # 1. 持仓股票关键词（最相关）
    holding_stock_codes, stock_keywords = extract_holding_keywords(fund_code)
    stock_codes.extend(holding_stock_codes)
    for kw in stock_keywords:
        if kw not in search_terms:
            search_terms.append(kw)

    # 2. 用户提供的关键词
    if keywords:
        for kw in keywords:
            if kw and kw not in search_terms:
                search_terms.append(kw)

    # 3. 基金代码和名称（兜底）
    search_terms.append(fund_code)
    if fund_name:
        core_name = fund_name.split("(")[0].split("（")[0].strip()
        if core_name not in search_terms:
            search_terms.append(core_name)
        for kw in _infer_fund_theme_keywords(fund_name):
            if kw not in search_terms:
                search_terms.append(kw)

    cutoff = _shared_today() - timedelta(days=days)

    # 个股新闻接口只适合股票代码，不适合中文关键词。
    for code in stock_codes:
        try:
            df = ak.stock_news_em(symbol=code)
            _append_news_from_df(all_news, seen, df, cutoff, source_hint=f"东方财富个股新闻:{code}")
        except Exception:
            continue

    # 全市场新闻兜底：先抓通用新闻，再用基金/行业/持仓关键词本地过滤。
    for df, source_hint in _fetch_market_news_frames(ak, days):
        _append_news_from_df(
            all_news,
            seen,
            df,
            cutoff,
            source_hint=source_hint,
            include_terms=search_terms,
        )

    all_news.sort(key=lambda x: x.get("date", ""), reverse=True)
    return all_news


def _fetch_market_news_frames(ak, days: int):
    frames = []
    for symbol in ["全部", "重点"]:
        try:
            frames.append((ak.stock_info_global_cls(symbol=symbol), f"财联社电报:{symbol}"))
        except Exception:
            pass
    try:
        frames.append((ak.stock_news_main_cx(), "财新数据通"))
    except Exception:
        pass

    # 央视新闻联播作为宏观兜底，最多回看 3 天，避免请求过多。
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
    if not text:
        return False
    normalized = text.lower()
    for term in terms:
        term = str(term).strip()
        if len(term) < 2:
            continue
        if term.lower() in normalized:
            return True
    return False


def _infer_fund_theme_keywords(fund_name: str) -> List[str]:
    name = fund_name or ""
    mapping = {
        "纳斯达克": ["纳斯达克", "美股", "科技股", "人工智能", "英伟达", "微软", "苹果"],
        "QDII": ["美股", "港股", "海外市场", "美元", "人民币汇率"],
        "新兴市场": ["新兴市场", "美元", "汇率", "全球市场"],
        "石油": ["石油", "原油", "天然气", "OPEC"],
        "天然气": ["天然气", "原油", "能源"],
        "新能源": ["新能源", "锂电", "电池", "汽车"],
        "电池": ["电池", "锂电", "新能源车"],
    }
    terms = []
    for key, values in mapping.items():
        if key in name:
            terms.extend(values)
    return terms


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
