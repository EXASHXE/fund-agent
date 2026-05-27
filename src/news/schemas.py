"""新闻模块数据结构定义"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class EntityProfile:
    """基金持仓实体画像"""
    fund_code: str
    fund_name: str
    stock_codes: List[str] = field(default_factory=list)
    stock_names: List[str] = field(default_factory=list)
    holdings: List[Dict] = field(default_factory=list)
    sector_keywords: List[str] = field(default_factory=list)
    theme_keywords: List[str] = field(default_factory=list)
    updated_at: Optional[str] = None
