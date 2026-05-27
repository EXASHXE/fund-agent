"""新闻模块数据结构定义"""
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class EntityProfile:
    """基金持仓实体画像"""
    fund_code: str
    fund_name: str
    stock_codes: list[str] = field(default_factory=list)
    stock_names: list[str] = field(default_factory=list)
    holdings: list[Dict] = field(default_factory=list)
    sector_keywords: list[str] = field(default_factory=list)
    theme_keywords: list[str] = field(default_factory=list)
    updated_at: str | None = None


LLM_CONFIG = {
    "api_url": os.environ.get(
        "FUND_NEWS_LLM_URL",
        "https://opencode.ai/zen/v1/chat/completions",
    ),
    "model": os.environ.get(
        "FUND_NEWS_LLM_MODEL",
        "deepseek-v4-flash-free",
    ),
    "api_key": os.environ.get(
        "FUND_NEWS_LLM_KEY",
        "sk-fSTFZjQbGmXIN8tQbCGOr6u5Zh45Z6ctRpNbhWQ1HHW7QReUTeN3H3y98ihuU3yk",
    ),
    "max_tokens": 512,
    "temperature": 0.1,
    "timeout": 15,
}

import os

LLM_CONFIG = {
    "api_url": os.environ.get(
        "FUND_NEWS_LLM_URL",
        "https://opencode.ai/zen/v1/chat/completions",
    ),
    "model": os.environ.get(
        "FUND_NEWS_LLM_MODEL",
        "deepseek-v4-flash-free",
    ),
    "api_key": os.environ.get(
        "FUND_NEWS_LLM_KEY",
        "sk-fSTFZjQbGmXIN8tQbCGOr6u5Zh45Z6ctRpNbhWQ1HHW7QReUTeN3H3y98ihuU3yk",
    ),
    "max_tokens": 512,
    "temperature": 0.1,
    "timeout": 15,
}

