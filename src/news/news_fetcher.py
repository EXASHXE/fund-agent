"""AKShare 新闻采集 — 按基金重仓股票和关键词获取相关新闻"""
from datetime import date, timedelta
from typing import List, Dict
import hashlib


def extract_holding_keywords(fund_code: str, limit: int = 10) -> List[str]:
    """从基金持仓中提取股票名称作为新闻搜索关键词。"""
    keywords = []
    for year in ["2025", "2024"]:
        try:
            import akshare as ak
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
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
    return result[:8]


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

    # 1. 持仓股票关键词（最相关）
    stock_keywords = extract_holding_keywords(fund_code)
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

    for term in search_terms:
        try:
            df = ak.stock_news_em(symbol=term)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = str(row.get("新闻标题", row.get("标题", "")))
                    content = str(row.get("新闻内容", row.get("内容", "")))
                    date_raw = str(row.get("发布时间", row.get("发布日期", "")))
                    source = str(row.get("文章来源", row.get("来源", "")))
                    url = str(row.get("新闻链接", row.get("链接", "")))

                    news_date = _parse_date(date_raw)

                    if news_date:
                        cutoff = date.today() - timedelta(days=days)
                        if news_date < cutoff:
                            continue

                    digest = hashlib.md5(title.encode()).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)

                    all_news.append({
                        "title": title,
                        "content": content[:500],
                        "date": news_date.isoformat() if news_date else "",
                        "source": source,
                        "url": url,
                    })
        except Exception:
            continue

    all_news.sort(key=lambda x: x.get("date", ""), reverse=True)
    return all_news


def _parse_date(date_str: str) -> date:
    """解析多种日期格式"""
    if not date_str:
        return None
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
        try:
            from datetime import datetime
            return datetime.strptime(str(date_str)[:10], fmt).date()
        except ValueError:
            continue
    return None

