"""AKShare 新闻采集 — 按基金重仓股票和关键词获取相关新闻"""
from datetime import date, timedelta
from src.config.shared import today as _shared_today
from typing import List, Dict, Tuple
import hashlib
import re
import sys
import requests
import json
import pandas as pd
from datetime import datetime
from threading import RLock

_AK_CACHE = {}
_LAST_AK_MODULE = None
_AK_CACHE_LOCK = RLock()

def _cached_ak_call(func_name: str, *args, **kwargs):
    """带缓存的 AKShare 调用，支持在 sys.modules['akshare'] 变更（如测试 Mock）时自动清空缓存。"""
    global _LAST_AK_MODULE, _AK_CACHE
    current_ak = sys.modules.get("akshare")

    key = (func_name, str(args), str(sorted(kwargs.items())))
    with _AK_CACHE_LOCK:
        if current_ak is not _LAST_AK_MODULE:
            _AK_CACHE.clear()
            _LAST_AK_MODULE = current_ak
        if key in _AK_CACHE:
            return _AK_CACHE[key]

    import akshare as ak
    func = getattr(ak, func_name)
    
    import time
    last_exc = None
    for attempt in range(3):
        try:
            res = func(*args, **kwargs)
            with _AK_CACHE_LOCK:
                _AK_CACHE[key] = res
            return res
        except Exception as e:
            last_exc = e
            print(f"  [WARNING] AKShare.{func_name} 调用失败 (第 {attempt + 1}/3 次): {e}")
            if attempt < 2:
                time.sleep(1.0)
                
    raise last_exc


_GLOBAL_STOCK_TRANSLATIONS = {
    "NVIDIA": "英伟达",
    "NVDA": "英伟达",
    "TSMC": "台积电",
    "ASML": "阿斯麦",
    "Microsoft": "微软",
    "MSFT": "微软",
    "Apple": "苹果",
    "AAPL": "苹果",
    "Amazon": "亚马逊",
    "AMZN": "亚马逊",
    "Alphabet": "谷歌",
    "Google": "谷歌",
    "GOOG": "谷歌",
    "GOOGL": "谷歌",
    "Meta": "脸书",
    "Facebook": "脸书",
    "Broadcom": "博通",
    "AVGO": "博通",
    "Qualcomm": "高通",
    "QCOM": "高通",
    "Tesla": "特斯拉",
    "TSLA": "特斯拉",
    "AMD": "超威半导体",
    "Intel": "英特尔",
    "INTC": "英特尔",
    "Netflix": "奈飞",
    "NFLX": "奈飞",
    "Micron": "美光",
    "MU": "美光",
    "Eli Lilly": "礼来",
    "LLY": "礼来",
    "Novo Nordisk": "诺和诺德",
    "NVO": "诺和诺德",
    "Lumentum": "路门特姆",
    "LITE": "路门特姆",
    "Coherent": "科赫特",
    "COHR": "科赫特",
    "Samsung": "三星",
    "Tencent": "腾讯",
    "Alibaba": "阿里巴巴",
    "HDFC": "HDFC银行",
    "ICICI": "ICICI银行",
}


def _parse_float_pct(value) -> float:
    """Parse a percent value to float (e.g. '7.79' → 7.79, '5%' → 5.0)."""
    try:
        raw = str(value).strip()
        if raw.endswith("%"):
            return float(raw[:-1])
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def extract_holding_keywords(fund_code: str, limit: int = 10) -> Tuple[List[str], List[str]]:
    """从基金最新重仓中提取股票代码和名称关键词。"""
    stock_codes = []
    keywords = []
    for year in ["2025", "2024"]:
        try:
            df = _cached_ak_call("fund_portfolio_hold_em", symbol=fund_code, date=year)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    code = str(row.get("股票代码", "")).strip()
                    if code and code.lower() != "nan":
                        stock_codes.append(code)
                    name = _normalize_company_name(str(row.get("股票名称", "")))
                    
                    # 尝试匹配全球/美港股的中文简称
                    translated_kw = None
                    for eng_key, chi_val in _GLOBAL_STOCK_TRANSLATIONS.items():
                        if eng_key.lower() in name.lower() or eng_key.lower() == code.lower():
                            translated_kw = chi_val
                            break

                    if name and len(name) >= 2:
                        keywords.append(name)
                    if translated_kw and translated_kw not in keywords:
                        keywords.append(translated_kw)
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
    # 重仓股始终提取（个股新闻路径需要 stock_codes，不受 agent_keywords 影响）
    stock_codes, stock_keywords = extract_holding_keywords(fund_code, limit=limit)

    # Extract weights for search budget
    stock_weights = {}
    try:
        for year in ["2025", "2024"]:
            try:
                df = _cached_ak_call("fund_portfolio_hold_em", symbol=fund_code, date=year)
                if df is not None and not df.empty:
                    for _, row in df.head(limit).iterrows():
                        code = str(row.get("股票代码", "")).strip()
                        weight = _parse_float_pct(row.get("占净值比例", 0))
                        if code and code.lower() != "nan":
                            stock_weights[code] = weight
                    break
            except Exception:
                continue
    except Exception:
        pass

    profile = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "stock_codes": stock_codes,
        "holding_keywords": stock_keywords,
        "agent_keywords": agent_keywords or [],
        "fallback_keywords": _fallback_fund_keywords(fund_name, fund_type),
        "stock_weights": stock_weights,
    }
    terms = []
    # 优先用重仓股名和 Agent 关键词（精准匹配）
    for group in ["holding_keywords", "agent_keywords"]:
        for kw in profile[group]:
            if kw and kw not in terms:
                terms.append(kw)
    # 仅当持仓关键词不足 5 个时才启用兜底词（防止泛词污染）
    if len(terms) < 5:
        for kw in profile["fallback_keywords"]:
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
    shared_seen: set = None,
    max_items: int = 50,
    as_of: date = None,
) -> List[Dict]:
    """获取与基金相关的近期新闻。优先按重仓股票搜索，次选基金名称/代码。

    shared_seen: 跨基金去重集合。传入后同一新闻不会在不同基金间重复出现。
    """
    try:
        import akshare as ak
    except ImportError:
        return []

    all_news = []
    seen = shared_seen if shared_seen is not None else set()

    profile = build_news_search_profile(
        fund_code=fund_code,
        fund_name=fund_name,
        fund_type=fund_type,
        agent_keywords=keywords,
    )
    search_terms = profile["search_terms"]
    stock_codes = profile["stock_codes"]

    reference_date = as_of or _shared_today()
    cutoff = reference_date - timedelta(days=days)

    # 个股新闻接口只适合股票代码，不适合中文关键词。
    stock_weights = profile.get("stock_weights", {})
    for code in stock_codes:
        weight = stock_weights.get(code, 0)
        if weight < 2.0:
            continue
        try:
            df = _cached_ak_call("stock_news_em", symbol=code)
            _append_news_from_df(
                all_news, seen, df, cutoff,
                source_hint=f"东方财富个股新闻:{code}",
                max_date=reference_date,
                forced_match_term=code,
            )
        except Exception:
            continue

    # 全市场新闻兜底：先抓通用新闻，再用基金/行业/持仓关键词本地过滤。
    fund_profile = {"name": fund_name, "type": fund_type, "keywords": search_terms}
    market_frames = list(_fetch_market_news_frames(days, fund_profile=fund_profile, as_of=reference_date))
    for df, source_hint in market_frames:
        _append_news_from_df(
            all_news,
            seen,
            df,
            cutoff,
            source_hint=source_hint,
            include_terms=search_terms,
            max_date=reference_date,
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
                    max_date=reference_date,
                )

    all_news.sort(key=lambda x: (x.get("date", ""), x.get("match_score", 0)), reverse=True)
    return all_news[:max_items]


def _fetch_market_news_frames(days: int, fund_profile: Dict = None, as_of: date = None):
    frames = []

    # 扩展数据源：新浪财经滚动新闻兜底（比 AKShare 更稳定）
    try:
        frames.append((_fetch_sina_roll_news_df(pages=5), "新浪财经滚动"))
    except Exception:
        pass

    # 财联社电报全量流（时效性更强、数据量更大）
    try:
        frames.append((_cached_ak_call("stock_telegraph_cls"), "财联社电报全量"))
    except Exception:
        pass

    # 财联社分类电报
    for symbol in ["全部", "重点"]:
        try:
            frames.append((_cached_ak_call("stock_info_global_cls", symbol=symbol), f"财联社电报:{symbol}"))
        except Exception:
            pass

    # 行业新闻：只拉与该基金主题相关的行业，避免泛匹配
    industries = _fund_industries(fund_profile) if fund_profile else []
    for industry in industries:
        try:
            frames.append((_cached_ak_call("stock_info_global_cls", symbol=industry), f"行业新闻:{industry}"))
        except Exception:
            pass

    try:
        frames.append((_cached_ak_call("stock_news_main_cx"), "财新数据通"))
    except Exception:
        pass

    # 新闻联播（最多回看 3 天）
    for i in range(min(days, 3)):
        d = ((as_of or _shared_today()) - timedelta(days=i)).strftime("%Y%m%d")
        try:
            frames.append((_cached_ak_call("news_cctv", date=d), f"新闻联播:{d}"))
        except Exception:
            pass

    return frames


def _fetch_sina_roll_news_df(pages: int = 5):
    """通过新浪财经API获取实时滚动新闻，作为坚实的数据源扩展。"""
    rows = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for page in range(1, pages + 1):
        url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=50&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            data = resp.json()
            items = data.get('result', {}).get('data', [])
            for item in items:
                dt = datetime.fromtimestamp(int(item.get('ctime', 0)))
                rows.append({
                    "title": item.get('title', ''),
                    "summary": item.get('summary', ''),
                    "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "新浪财经",
                    "url": item.get('url', '')
                })
        except Exception:
            continue
    return pd.DataFrame(rows) if rows else None


def _append_news_from_df(
    all_news: List[Dict],
    seen: set,
    df,
    cutoff: date,
    source_hint: str = "",
    include_terms: List[str] = None,
    max_date: date = None,
    forced_match_term: str = None,
):
    if df is None or getattr(df, "empty", True):
        return

    for _, row in df.iterrows():
        title = _pick_first(row, ["新闻标题", "标题", "title", "内容标题", "事件标题"])
        content = _pick_first(row, ["新闻内容", "内容", "摘要", "summary", "事件内容", "详情"])
        date_raw = _pick_first(row, ["发布时间", "发布日期", "时间", "日期", "date", "datetime", "新闻时间"])
        source = _pick_first(row, ["文章来源", "来源", "source"]) or source_hint
        url = _pick_first(row, ["新闻链接", "链接", "url", "网址"])

        text = f"{title} {content}".strip()
        if not title and not content:
            continue

        # 关键词过滤：优先匹配标题（精准），标题无命中再降级到全文
        matched_terms = []
        match_scope = ""
        match_score = 0
        if include_terms:
            title_matches = _matched_terms(title or "", include_terms)
            content_matches = _matched_terms(content or "", include_terms) if not title_matches else []
            if not title_matches and not content_matches:
                continue
            if title_matches:
                matched_terms = title_matches
                match_scope = "title"
                match_score = 2
            else:
                matched_terms = content_matches
                match_scope = "content"
                match_score = 1
        elif forced_match_term:
            matched_terms = [forced_match_term]
            match_scope = "forced"
            match_score = 2

        news_date = _parse_date(date_raw)
        if news_date and news_date < cutoff:
            continue
        if news_date and max_date and news_date > max_date:
            continue

        # 去重：以标准化标题为 key（不同来源的同标题新闻只保留一条）
        dedup_key = hashlib.md5(title.encode() if title else content[:80].encode()).hexdigest()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        all_news.append({
            "title": title or content[:80],
            "content": content[:500],
            "date": news_date.isoformat() if news_date else "",
            "source": source,
            "url": url,
            "matched_terms": matched_terms,
            "match_scope": match_scope,
            "match_score": match_score,
        })


def _pick_first(row, names: List[str]) -> str:
    for name in names:
        if name in row and row.get(name) is not None:
            value = str(row.get(name)).strip()
            if value and value.lower() != "nan":
                return value
    return ""


def _matches_terms(text: str, terms: List[str]) -> bool:
    """中英文匹配：英文启用词边界，中文保持子串匹配。"""
    return bool(_matched_terms(text, terms))


def _matched_terms(text: str, terms: List[str]) -> List[str]:
    """Return matched search terms with word-boundary awareness for English terms."""
    if not text:
        return []
    text_lower = text.lower()
    matched = []
    for term in terms:
        term = str(term).strip()
        if len(term) < 2:
            continue
        term_lower = term.lower()
        if term_lower.isascii():
            pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE | re.ASCII)
            if pattern.search(text):
                matched.append(term)
        else:
            if term_lower in text_lower:
                matched.append(term)
    return matched


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

    # 公募主题词 → 行业关键词映射（只保留高相关性词组，避免泛词污染）
    _THEME_MAP = {
        "纳斯达克": ["纳斯达克", "美股科技", "AI"],
        "标普": ["标普500", "美股"],
        "恒生": ["恒生指数", "港股"],
        "黄金": ["黄金", "贵金属"],
        "石油": ["原油", "石油", "能源"],
        "天然气": ["天然气", "能源"],
        "新兴市场": ["新兴市场经济体"],
        "半导体": ["半导体", "芯片"],
        "新能源": ["新能源", "锂电池", "光伏"],
        "医药": ["医药", "创新药"],
        "消费": ["消费", "白酒"],
        "电池": ["锂电池", "新能源车"],
        "油气": ["原油", "石油"],
    }
    matched_themes = set()
    for theme, kws in _THEME_MAP.items():
        if theme in text:
            matched_themes.add(theme)
            for kw in kws:
                if kw not in terms:
                    terms.append(kw)

    # 无具体主题的 QDII 兜底（不含"汇率"——太泛，误配率高）
    if ("QDII" in text or "qdii" in text.lower()) and not matched_themes:
        terms.append("QDII")

    if "债" in text:
        terms.extend(["利率债", "信用债"])
    return terms


def _fund_industries(fund_profile: Dict) -> List[str]:
    """从基金画像提取相关申万行业名，用于定向拉取行业新闻。"""
    if not fund_profile:
        return []
    text = f"{fund_profile.get('name', '')} {fund_profile.get('type', '')}"
    kws = fund_profile.get("keywords", [])
    kw_text = " ".join(str(k) for k in kws)

    industries = set()
    _INDUSTRY_THEME_MAP = {
        # 半导体链条
        "半导体": "半导体",
        "芯片": "半导体",
        "AI芯片": "半导体",
        "光刻机": "半导体",
        "刻蚀机": "半导体",
        "光刻": "半导体",
        "闪存": "半导体",
        "HBM": "半导体",
        "先进封装": "半导体",
        "CMP": "半导体",
        "薄膜沉积": "半导体",
        "晶圆": "半导体",
        "国产替代": "半导体",
        "ASIC": "半导体",
        "检测设备": "半导体",
        "存储": "半导体",
        # 算力（替代原来的"科技"）
        "算力": "算力",
        "数据中心": "算力",
        "光模块": "算力",
        # 新能源
        "新能源": "新能源",
        "锂电池": "新能源",
        "光伏": "新能源",
        "电池": "新能源",
        "新能源车": "新能源",
        "固态电池": "新能源",
        "储能": "新能源",
        "锂电": "新能源",
        "动力电池": "新能源",
        "碳酸锂": "新能源",
        "换电": "新能源",
        # 能源
        "石油": "能源",
        "原油": "能源",
        "天然气": "能源",
        "能源": "能源",
        "LNG": "能源",
        "油服": "能源",
        "石化": "能源",
        "钻井平台": "能源",
        "油气": "能源",
        # 医药
        "医药": "医药",
        "创新药": "医药",
        # 消费
        "消费": "消费",
        "白酒": "消费",
        # 有色
        "黄金": "有色",
        "贵金属": "有色",
        # 全球/新兴
        "新兴市场": "全球",
        "港股": "全球",
        "韩国半导体": "半导体",
    }
    full_text = f"{text} {kw_text}"
    for theme, industry in _INDUSTRY_THEME_MAP.items():
        if theme in full_text:
            industries.add(industry)

    return sorted(industries) if industries else []


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
