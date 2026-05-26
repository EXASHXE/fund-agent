"""Quantitative metrics: Sortino, Alpha, Beta, IR, HHI, win-rate, Calmar."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from src.config.defaults import QUANT_CONFIG


class MetricsCalculator:
    def sortino_ratio(self, daily_returns: list | None, mar_annual: float | None = None) -> float:
        """计算索提诺比率（Sortino Ratio）"""
        if not daily_returns or len(daily_returns) < 20:
            return 0.0

        if mar_annual is None:
            mar_annual = QUANT_CONFIG.get("SORTINO_MAR", 0.025)

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

    def advanced_metrics(self, nav_df, basic: dict) -> dict:
        if nav_df is None or (hasattr(nav_df, "empty") and nav_df.empty) or "日增长率" not in nav_df.columns:
            return {}

        returns = nav_df["日增长率"].dropna().values / 100.0
        if len(returns) < 60:
            return {}

        ftype = basic.get("fund_type", "")
        is_qdii = "QDII" in ftype

        try:
            import akshare as ak
            if is_qdii:
                bench_df = ak.index_us_stock_sina(symbol=".IXIC")
                bench_df["date"] = pd.to_datetime(bench_df["date"])
                bench_df["return"] = bench_df["close"].pct_change()
            else:
                bench_df = ak.stock_zh_index_daily(symbol="sh000300")
                bench_df["date"] = pd.to_datetime(bench_df["date"])
                bench_df["return"] = bench_df["close"].pct_change()
            bench_returns = bench_df["return"].dropna().values
            bench_returns = bench_returns[-len(returns):] if len(bench_returns) > len(returns) else bench_returns
        except Exception:
            return {}

        if len(bench_returns) < 30:
            return {}

        min_len = min(len(returns), len(bench_returns))
        fund_r = returns[-min_len:]
        bench_r = bench_returns[-min_len:]

        rf_daily = 0.025 / 252

        cov = np.cov(fund_r, bench_r)[0][1]
        var = np.var(bench_r)
        beta = cov / var if var > 0 else 1.0

        excess = fund_r - bench_r
        ir = (np.mean(excess) / np.std(excess)) * np.sqrt(252) if np.std(excess) > 0 else 0

        alpha = (np.mean(fund_r - rf_daily) - beta * np.mean(bench_r - rf_daily)) * 252

        treynor = (np.mean(fund_r - rf_daily) * 252) / beta if abs(beta) > 1e-6 else 0

        returns_1y = returns[-252:] if len(returns) >= 252 else returns
        win_rate_1y = np.sum(returns_1y > 0) / len(returns_1y) * 100 if len(returns_1y) > 0 else 0

        cum_1y = (1 + pd.Series(returns_1y)).cumprod()
        rolling_max_1y = cum_1y.expanding().max()
        dd_1y = abs(((cum_1y - rolling_max_1y) / rolling_max_1y).min()) * 100 if len(cum_1y) > 0 else 0

        ann_return_1y = np.mean(returns_1y) * 252 * 100
        calmar_1y = ann_return_1y / dd_1y if dd_1y > 0 else 0

        return {
            "information_ratio": round(float(ir), 4),
            "jensen_alpha": round(float(alpha), 4),
            "treynor_ratio": round(float(treynor), 4),
            "beta": round(float(beta), 4),
            "win_rate_1y": round(float(win_rate_1y), 2),
            "calmar_ratio_1y": round(float(calmar_1y), 2),
        }

    def compute_perf_from_nav(self, nav_df) -> dict:
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
            "近1年": {"annual_volatility": round(vol_1y, 2),
                       "sharpe_ratio": round(float(sharpe_1y), 2),
                       "max_drawdown": round(float(dd_1y), 2)},
            "近3年": {"annual_volatility": round(vol_3y, 2),
                       "sharpe_ratio": round(float(sharpe_3y), 2),
                       "max_drawdown": round(float(dd_3y), 2)},
        }
