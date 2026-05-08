"""Pearson 相关性矩阵计算"""
import pandas as pd
from typing import Dict


def compute_correlations(funds_data: Dict) -> pd.DataFrame:
    """计算持仓基金间的 Pearson 相关系数。"""
    codes = list(funds_data.keys())
    nav_series = {}

    for code in codes:
        nav_df = funds_data[code].get("nav", pd.DataFrame())
        if not nav_df.empty and "日增长率" in nav_df.columns:
            returns = nav_df["日增长率"].dropna()
            if len(returns) > 30:
                nav_series[code] = returns

    if len(nav_series) < 2:
        return pd.DataFrame()

    merged = pd.DataFrame(nav_series)
    merged = merged.dropna()
    if len(merged) < 30:
        return pd.DataFrame()

    return merged.corr()
