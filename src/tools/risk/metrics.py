"""Pure risk/metric functions extracted from the legacy analysis modules.

Extracted from:
  - legacy/analysis/metrics.py      -> sortino_ratio, compute_perf_from_nav
  - legacy/analysis/correlation.py   -> compute_correlations
  - legacy/analysis/stress.py        -> stress_test, _fund_exposure_text, _infer_risk_scenarios

All functions are PURE: zero IO, zero network, zero LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

_DEFAULT_SORTINO_MAR = 0.025


# ====================================================================
# From legacy/analysis/metrics.py (MetricsCalculator class methods)
# ====================================================================


def sortino_ratio(daily_returns: list | None, mar_annual: float | None = None) -> float:
    """计算索提诺比率（Sortino Ratio）

    Pure numpy — no IO, no network, no LLM.
    """
    if not daily_returns or len(daily_returns) < 20:
        return 0.0

    if mar_annual is None:
        mar_annual = _DEFAULT_SORTINO_MAR

    returns = np.array(daily_returns, dtype=float)
    mar_daily = (1 + mar_annual) ** (1 / 252) - 1

    downside = np.minimum(returns - mar_daily, 0)
    downside_deviation_daily = np.sqrt(np.mean(downside ** 2))
    downside_deviation_annual = downside_deviation_daily * np.sqrt(252)

    if downside_deviation_annual == 0:
        return 0.0

    mean_excess_daily = np.mean(returns - mar_daily)
    sortino = mean_excess_daily * 252 / downside_deviation_annual

    return round(float(sortino), 4)


def compute_perf_from_nav(nav_df: Any) -> dict:
    """Compute Sharpe, volatility, max drawdown from NAV DataFrame.

    Pure pandas/numpy — no IO, no network, no LLM.
    """
    if nav_df is None or (hasattr(nav_df, "empty") and nav_df.empty) or "日增长率" not in nav_df.columns:
        return {"近1年": {}, "近3年": {}}

    returns = nav_df["日增长率"].dropna().values / 100.0
    if len(returns) < 30:
        return {"近1年": {}, "近3年": {}}

    if len(returns) >= 252:
        returns_1y = returns[-252:]
        vol_1y = np.std(returns_1y) * np.sqrt(252) * 100
        excess_1y = returns_1y - (0.025 / 252)
        sharpe_1y = (np.mean(excess_1y) / np.std(excess_1y)) * np.sqrt(252) if np.std(excess_1y) > 0 else 0
        cum_1y = (1 + pd.Series(returns_1y)).cumprod()
        rolling_max_1y = cum_1y.expanding().max()
        dd_1y = abs(((cum_1y - rolling_max_1y) / rolling_max_1y).min()) * 100 if len(cum_1y) > 0 else 0
    else:
        vol_1y = np.std(returns) * np.sqrt(252) * 100
        excess_1y = returns - (0.025 / 252)
        sharpe_1y = (np.mean(excess_1y) / np.std(excess_1y)) * np.sqrt(252) if np.std(excess_1y) > 0 else 0
        dd_1y = 0

    vol_3y = np.std(returns) * np.sqrt(252) * 100
    excess_3y = returns - (0.025 / 252)
    sharpe_3y = (np.mean(excess_3y) / np.std(excess_3y)) * np.sqrt(252) if np.std(excess_3y) > 0 else 0
    cum_all = (1 + pd.Series(returns)).cumprod()
    rolling_max_all = cum_all.expanding().max()
    dd_3y = abs(((cum_all - rolling_max_all) / rolling_max_all).min()) * 100 if len(cum_all) > 0 else 0

    return {
        "近1年": {
            "annual_volatility": round(vol_1y, 2),
            "sharpe_ratio": round(float(sharpe_1y), 2),
            "max_drawdown": round(float(dd_1y), 2),
        },
        "近3年": {
            "annual_volatility": round(vol_3y, 2),
            "sharpe_ratio": round(float(sharpe_3y), 2),
            "max_drawdown": round(float(dd_3y), 2),
        },
    }


# ====================================================================
# From legacy/analysis/correlation.py
# ====================================================================


def compute_correlations(funds_data: Dict) -> pd.DataFrame:
    """计算持仓基金间的 Pearson 相关系数。

    Pure pandas — no IO, no network, no LLM.
    """
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
    corr_df = merged.corr(min_periods=30)

    if corr_df.empty or corr_df.isna().all().all():
        return pd.DataFrame()

    return corr_df


# ====================================================================
# From legacy/analysis/stress.py
# ====================================================================


def stress_test(funds_data: Dict) -> List[Dict]:
    """按当前持仓暴露生成压力测试候选。

    Pure rule-based scenario generation — no IO, no network, no LLM.
    """
    results = []
    for code, fund in funds_data.items():
        basic = fund.get("basic", {}) or {}
        name = basic.get("name", "")
        ftype = basic.get("fund_type", "")
        exposure_text = _fund_exposure_text(fund)
        for scenario in _infer_risk_scenarios(name, ftype, exposure_text):
            results.append({
                "scenario_id": scenario["id"],
                "scenario_desc": scenario["desc"],
                "fund_code": code,
                "fund_name": name,
                "estimated_drawdown_pct": scenario["seed_drawdown"],
                "risk_driver": scenario["driver"],
                "agent_review_required": True,
                "agent_instruction": (
                    "这是基于持仓暴露生成的压力测试初稿。请结合最新宏观、行业、"
                    "新闻和组合仓位，自主调整冲击假设与影响金额。"
                ),
            })
    return results


def _fund_exposure_text(fund: Dict) -> str:
    """Extract a text summary of fund exposure for scenario matching."""
    parts = []
    for key in ["basic"]:
        value = fund.get(key, {})
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    for key in ["holdings", "sectors"]:
        df = fund.get(key)
        if df is not None and hasattr(df, "head") and not getattr(df, "empty", True):
            try:
                parts.append(" ".join(str(x) for x in df.head(10).astype(str).values.flatten()))
            except Exception:
                pass
    return " ".join(parts)


_RISK_RULES = [
    ("R_SEMI", ["半导体", "芯片", "寒武纪", "精测电子", "集成电路"], "国内半导体景气/估值回撤", "半导体需求不及预期、出口管制或估值收缩", -10.0),
    ("R_AI", ["AI", "人工智能", "算力", "服务器", "光模块"], "AI算力链交易拥挤", "业绩兑现低于高预期或资金从AI链撤出", -9.0),
    ("R_EV", ["新能源", "电池", "锂电", "光伏", "储能", "电动车"], "新能源供需和价格压力", "产能过剩、价格战或政策补贴边际变化", -8.0),
    ("R_QDII", ["QDII", "纳斯达克", "标普", "美元", "美股"], "海外权益与汇率共振", "美股估值回撤、美元/人民币波动或海外流动性收紧", -7.0),
    ("R_RATE", ["债", "固收", "利率", "信用"], "利率和信用利差冲击", "利率上行、信用利差扩大或赎回压力", -3.0),
    ("R_COMMODITY", ["石油", "原油", "黄金", "商品", "能源"], "商品价格大幅波动", "供需预期逆转或地缘事件降温", -8.0),
    ("R_CONSUMER", ["消费", "白酒", "食品", "医药", "医疗"], "内需和政策预期变化", "消费复苏弱于预期、集采/监管或盈利下修", -6.0),
]


def _infer_risk_scenarios(name: str, ftype: str, exposure_text: str) -> List[Dict]:
    """Match fund characteristics to predefined risk scenarios."""
    text = f"{name} {ftype} {exposure_text}"
    scenarios = []
    for sid, keywords, desc, driver, seed in _RISK_RULES:
        if any(kw in text for kw in keywords):
            scenarios.append({
                "id": sid,
                "desc": desc,
                "driver": driver,
                "seed_drawdown": seed,
            })
    if not scenarios:
        scenarios.append({
            "id": "R_MARKET",
            "desc": "权益市场系统性波动",
            "driver": "风险偏好下降、资金面收紧或指数回撤",
            "seed_drawdown": -6.0,
        })
    return scenarios
