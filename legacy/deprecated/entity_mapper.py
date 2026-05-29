"""持仓实体画像构建器 —— 从基金重仓/行业配置生成 EntityProfile"""
from typing import List, Dict
from legacy.news.schemas import EntityProfile


# 行业 → 关键词白名单映射
_SECTOR_KEYWORD_MAP = {
    "白酒": ["白酒", "茅台", "五粮液", "泸州老窖", "消费"],
    "半导体": ["半导体", "芯片", "光刻机", "HBM", "台积电", "中芯国际", "英伟达", "ASML"],
    "新能源": ["锂电", "电池", "光伏", "储能", "固态电池", "钠离子", "宁德时代", "比亚迪"],
    "消费": ["消费", "电商", "零售", "食品", "饮料", "家电"],
    "医药": ["医药", "创新药", "CXO", "医疗器械", "百济神州"],
    "银行": ["银行", "城商行", "农商行", "息差", "不良率"],
    "算力": ["AI芯片", "数据中心", "光模块", "CPO", "英伟达", "算力"],
    "汽车": ["汽车", "智驾", "新能源车", "整车", "零部件"],
    "能源": ["石油", "原油", "天然气", "LNG", "OPEC", "煤炭"],
    "金融": ["券商", "保险", "非银", "资管"],
    "地产": ["地产", "房地产", "物业", "基建"],
    "有色": ["铜", "铝", "黄金", "稀土", "锂", "钴", "镍"],
}


# 股票别名映射
_STOCK_ALIAS = {
    "300750": ["宁德时代", "宁德", "CATL"],
    "002594": ["比亚迪", "BYD"],
    "600519": ["贵州茅台", "茅台"],
    "000858": ["五粮液"],
    "688981": ["中芯国际", "SMIC"],
    "688256": ["寒武纪"],
    "002460": ["赣锋锂业", "赣锋"],
    "300274": ["阳光电源"],
    "600036": ["招商银行"],
    "600900": ["长江电力"],
    "002415": ["海康威视"],
    "300124": ["汇川技术"],
}


def entity_profile_from_fund(
    fund_code: str,
    fund_name: str = "",
    holdings: list[Dict] = None,
    sectors: list[Dict] = None,
) -> EntityProfile:
    """从基金持仓和行业配置构建实体画像。

    Args:
        fund_code: 基金代码
        fund_name: 基金名称
        holdings: 重仓股列表 [{"stock_code": "...", "stock_name": "...", "weight": 0.08}, ...]
        sectors: 行业配置 [{"sector": "...", "weight": 0.15}, ...]

    Returns:
        EntityProfile 实体画像
    """
    holdings = holdings or []
    sectors = sectors or []

    stock_codes = []
    stock_names = []
    holding_entries = []

    for h in holdings[:10]:
        code = str(h.get("stock_code") or h.get("股票代码") or "").strip()
        name = str(h.get("stock_name") or h.get("股票名称") or "").strip()
        
        weight_val = h.get("weight")
        if weight_val is None:
            weight_val = h.get("占净值比例") or h.get("持仓占比") or h.get("占比") or h.get("持股占比") or 0.0
        
        # Safely parse weight
        weight = 0.0
        try:
            raw_w = str(weight_val).strip()
            if raw_w.endswith("%"):
                weight = float(raw_w[:-1])
            else:
                weight = float(raw_w)
        except (ValueError, TypeError):
            weight = 0.0

        if code and code.lower() != "nan":
            stock_codes.append(code)
        if name and name.lower() != "nan":
            stock_names.append(name)
        holding_entries.append({"stock_code": code, "stock_name": name, "weight": weight})

    # 补充别名
    for code in stock_codes:
        aliases = _STOCK_ALIAS.get(code, [])
        for alias in aliases:
            if alias not in stock_names:
                stock_names.append(alias)

    # 行业关键词
    sector_keywords = set()
    for s in (sectors or [])[:5]:
        sector_name = str(s.get("sector") or s.get("行业名称") or s.get("行业分类") or "").strip()
        if sector_name:
            sector_keywords.add(sector_name)
            for kw in _SECTOR_KEYWORD_MAP.get(sector_name, []):
                sector_keywords.add(kw)

    # 从重仓股名推断主题词
    theme_keywords = set()
    for name in stock_names:
        for sector, kws in _SECTOR_KEYWORD_MAP.items():
            if any(kw in name for kw in kws[:3]):
                theme_keywords.update(kws[:5])

    return EntityProfile(
        fund_code=fund_code,
        fund_name=fund_name or fund_code,
        stock_codes=list(dict.fromkeys(stock_codes)),
        stock_names=list(dict.fromkeys(stock_names)),
        holdings=holding_entries,
        sector_keywords=list(sector_keywords),
        theme_keywords=list(theme_keywords),
    )


def all_search_terms(profile: EntityProfile) -> list[str]:
    """汇总所有可用于搜索的关键词（去重优先）"""
    terms = []
    seen = set()
    for name in profile.stock_names:
        if name not in seen:
            terms.append(name)
            seen.add(name)
    for kw in profile.sector_keywords:
        if kw not in seen:
            terms.append(kw)
            seen.add(kw)
    for kw in profile.theme_keywords:
        if kw not in seen and len(terms) < 20:
            terms.append(kw)
            seen.add(kw)
    return terms
