# FundAnalyzer Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拆分 `src/analysis/scorer.py` (784行) 中 `FundAnalyzer` 的 5 个职责到独立模块，保持公开接口不变。

**Architecture:** 引入 Facade 模式 — `FundAnalyzer` 保留公开接口，内部委托给 `FundDataLoader`、`MacroScorer`/`MesoScorer`/`MicroScorer`、`FactorMatrixBuilder`、`MetricsCalculator`。先搬家不改变逻辑。

**Tech Stack:** Python 3.10+, pandas, numpy, pytest, unittest

---

### Task 1: Create MetricsCalculator

**Files:**
- Create: `src/analysis/metrics.py`
- Modify: `src/analysis/scorer.py`

- [ ] **Step 1: Create `src/analysis/metrics.py`**

Move `_compute_sortino_ratio` (module-level function) and `_compute_advanced_metrics` method logic into a new `MetricsCalculator` class.

```python
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
        """计算信息比率、詹森 Alpha、特雷诺比率等高级指标。

        Args:
            nav_df: 净值 DataFrame，含 "日增长率" 列
            basic: 基金基本信息 dict，含 "fund_type"

        Returns:
            包含 information_ratio, jensen_alpha, treynor_ratio, beta, win_rate_1y, calmar_ratio_1y 的 dict
        """
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
        """从净值数据自算波动率/最大回撤/夏普比率（perf API 失败时的降级方案）"""
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
```

- [ ] **Step 2: Wire MetricsCalculator into FundAnalyzer**

In `src/analysis/scorer.py`, import `MetricsCalculator` and delegate from existing methods:

Replace the `_compute_sortino_ratio` module-level function with a line at the top of scorer.py:

```python
from src.analysis.metrics import MetricsCalculator
```

Delete the `_compute_sortino_ratio` function entirely (move logic already in Step 1).

In `FundAnalyzer.__init__`, add `self._metrics = MetricsCalculator()`.

In `score_fund`, replace the sortino calculation block with:
```python
sortino_val = 0.0
nav_df = fund.get("nav")
if isinstance(nav_df, pd.DataFrame) and not nav_df.empty and "日增长率" in nav_df.columns:
    daily_returns = nav_df["日增长率"].dropna().values / 100.0
    if len(daily_returns) >= 20:
        sortino_val = self._metrics.sortino_ratio(daily_returns.tolist())
```

Replace `self._compute_advanced_metrics(code)` with:
```python
nav_df = fund.get("nav")
adv = self._metrics.advanced_metrics(nav_df, basic) if completeness in ("A", "B") else {}
```

Replace `self._compute_perf_from_nav(code)` with `self._metrics.compute_perf_from_nav(nav_df)` (pass nav_df directly, not code).

Update `_compute_advanced_metrics` method to be a thin delegate:
```python
def _compute_advanced_metrics(self, code: str) -> dict:
    fund = self.funds.get(code, {})
    nav_df = fund.get("nav")
    basic = fund.get("basic", {})
    return self._metrics.advanced_metrics(nav_df, basic)
```

Update `_compute_perf_from_nav(self, code: str) -> dict`:
```python
def _compute_perf_from_nav(self, code: str) -> dict:
    nav_df = self.funds[code].get("nav")
    result = self._metrics.compute_perf_from_nav(nav_df)
    self.funds[code]["perf"] = result
    return result
```

- [ ] **Step 3: Run tests to verify no regression**

```bash
python -m pytest tests/ -x --tb=short -q
```
Expected: 89 passed

- [ ] **Step 4: Commit**

```bash
git add src/analysis/metrics.py src/analysis/scorer.py
git commit -m "refactor: extract MetricsCalculator from FundAnalyzer"
```

---

### Task 2: Create FundDataLoader

**Files:**
- Create: `src/analysis/loader.py`
- Modify: `src/analysis/scorer.py`

- [ ] **Step 1: Create `src/analysis/loader.py`**

```python
"""Fund data loading and completeness assessment."""
from __future__ import annotations

import pandas as pd

from src.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure,
)


class FundDataLoader:
    def load_fund(self, code: str) -> dict:
        """Collect all data for a single fund. Returns a fund data dict."""
        basic = fetch_fund_basic(code)
        perf = fetch_fund_performance(code)
        nav = fetch_fund_nav(code)
        holdings = fetch_fund_holdings(code)
        sectors = fetch_fund_sectors(code)
        holders = fetch_holder_structure(code)

        fund_data = {
            "basic": basic,
            "perf": perf,
            "nav": nav,
            "holdings": holdings,
            "sectors": sectors,
            "holders": holders,
        }

        completeness = self._assess_completeness(basic, perf, nav, holdings, sectors)
        fund_data["completeness"] = completeness
        return fund_data

    def _assess_completeness(self, basic, perf, nav, holdings, sectors) -> str:
        has_basic = bool(basic) and "error" not in basic
        has_nav = isinstance(nav, pd.DataFrame) and len(nav) > 30
        has_perf = bool(perf) and "error" not in perf

        if not has_basic or not has_nav:
            return "D"

        core_ok = has_basic and has_nav
        enhanced_ok = (
            isinstance(holdings, pd.DataFrame) and len(holdings) > 0 and
            isinstance(sectors, pd.DataFrame) and len(sectors) > 0
        )

        if not core_ok:
            return "D"
        if has_perf and enhanced_ok:
            return "A"
        if has_perf:
            return "B"
        if core_ok and enhanced_ok:
            return "B"
        if core_ok:
            return "C"
        return "D"
```

- [ ] **Step 2: Wire FundDataLoader into FundAnalyzer**

In `src/analysis/scorer.py`, import:
```python
from src.analysis.loader import FundDataLoader
```

In `FundAnalyzer.__init__`, add:
```python
self._loader = FundDataLoader()
```

Replace `load_fund` method:
```python
def load_fund(self, code: str):
    print(f"  [Layer 1] 采集 {code} 数据...")
    fund_data = self._loader.load_fund(code)
    self.funds[code] = fund_data
    print(f"    完整度: {fund_data['completeness']}")
    return fund_data["completeness"]
```

Delete `_assess_completeness` method from `FundAnalyzer`.

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```
Expected: 89 passed

- [ ] **Step 4: Commit**

```bash
git add src/analysis/loader.py src/analysis/scorer.py
git commit -m "refactor: extract FundDataLoader from FundAnalyzer"
```

---

### Task 3: Create Scoring package (macro / meso / micro)

**Files:**
- Create: `src/analysis/scoring/__init__.py`
- Create: `src/analysis/scoring/macro.py`
- Create: `src/analysis/scoring/meso.py`
- Create: `src/analysis/scoring/micro.py`
- Modify: `src/analysis/scorer.py`

- [ ] **Step 1: Create `src/analysis/scoring/__init__.py`**

```python
"""Scoring strategies for macro, meso, and micro dimensions."""
from src.analysis.scoring.macro import MacroScorer
from src.analysis.scoring.meso import MesoScorer
from src.analysis.scoring.micro import MicroScorer

__all__ = ["MacroScorer", "MesoScorer", "MicroScorer"]
```

- [ ] **Step 2: Create `src/analysis/scoring/macro.py`**

```python
"""Macro scoring (weight: 20/100). Cycle fit + liquidity + valuation."""
from typing import Dict, Tuple


class MacroScorer:
    def score(self, code: str, fund_data: dict) -> Tuple[int, Dict, str]:
        fund = fund_data
        ft = fund.get("basic", {})
        fund_type = ft.get("fund_type", "domestic") if ft else "domestic"
        fund_name = ft.get("name", "") if ft else ""

        # 周期适配 (0-8)
        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name or "科技" in fund_name:
                cycle_score = 3
            elif "新兴市场" in fund_name:
                cycle_score = 5
            else:
                cycle_score = 4
        elif "指数" in fund_type or "ETF" in fund_type:
            if "石油" in fund_name or "能源" in fund_name:
                cycle_score = 4
            elif "新能源" in fund_name or "电池" in fund_name:
                cycle_score = 3
            else:
                cycle_score = 4
        elif "混合" in fund_type or "灵活" in fund_type:
            cycle_score = 5
        else:
            cycle_score = 4

        # 利率/流动性 (0-6)
        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            liquidity_score = 5
        else:
            liquidity_score = 5

        # 大盘估值 (0-6)
        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name:
                valuation_score = 2
            elif "新兴市场" in fund_name:
                valuation_score = 5
            else:
                valuation_score = 4
        elif "指数" in fund_type or "ETF" in fund_type:
            valuation_score = 4
        else:
            valuation_score = 5

        macro_total = min(20, cycle_score + liquidity_score + valuation_score)
        return macro_total, {}, ""
```

- [ ] **Step 3: Create `src/analysis/scoring/meso.py`**

```python
"""Meso scoring (weight: 30/100). Sector prosperity + valuation + policy + rotation."""
from typing import Dict, Optional, Tuple


class MesoScorer:
    def score(self, code: str, fund_data: dict, completeness: str) -> Tuple[Optional[int], Dict, str]:
        if completeness in ("C", "D"):
            return None, {}, ""

        fund = fund_data
        ft = fund.get("basic", {})
        fund_name = ft.get("name", "") if ft else ""
        fund_type = ft.get("fund_type", "domestic") if ft else "domestic"

        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            if "纳斯达克" in fund_name or "科技" in fund_name:
                prosperity, pe_score, policy, rotation = 4, 2, 4, 3
            elif "新兴市场" in fund_name:
                prosperity, pe_score, policy, rotation = 7, 6, 5, 5
            else:
                prosperity, pe_score, policy, rotation = 5, 4, 3, 3
        elif "石油" in fund_name or "能源" in fund_name:
            prosperity, pe_score, policy, rotation = 3, 3, 2, 2
        elif "新能源" in fund_name or "电池" in fund_name:
            prosperity, pe_score, policy, rotation = 3, 6, 4, 3
        elif "混合" in fund_type or "灵活" in fund_type:
            prosperity, pe_score, policy, rotation = 5, 5, 5, 4
        else:
            prosperity, pe_score, policy, rotation = 5, 4, 3, 3

        meso_total = min(30, prosperity + pe_score + policy + rotation)
        return meso_total, {}, ""
```

- [ ] **Step 4: Create `src/analysis/scoring/micro.py`**

```python
"""Micro scoring (weight: 50/100). Manager quality + Alpha persistence + drawdown + Sharpe + institutional holdings."""
from typing import Dict, Tuple


class MicroScorer:
    def score(self, code: str, fund_data: dict) -> Tuple[int, Dict, str]:
        fund = fund_data
        basic = fund["basic"]
        perf = fund.get("perf", {})
        details = {}

        perf_3y = perf.get("近3年", {})
        perf_1y = perf.get("近1年", {})
        ftype = basic.get("fund_type", "")

        # 1. 经理稳定性 (0-10)
        manager_name = basic.get("manager", "")
        if manager_name:
            manager_score = 8
            details["manager"] = manager_name
        else:
            manager_score = 5

        # 2. Alpha 持续性 (0-12)
        sharpe_3y = perf_3y.get("sharpe_ratio", 0) or 0
        if sharpe_3y > 1.5:
            alpha_score = 11
        elif sharpe_3y > 1.0:
            alpha_score = 9
        elif sharpe_3y > 0.5:
            alpha_score = 7
        elif sharpe_3y > 0:
            alpha_score = 4
        else:
            alpha_score = 3

        # 3. 最大回撤 vs 同类 (0-10)
        max_dd = perf_3y.get("max_drawdown", 30) or 30
        if "QDII" in ftype:
            peer_dd = 28
        elif "指数" in ftype or "ETF" in ftype:
            peer_dd = 30
        else:
            peer_dd = 22

        if max_dd < peer_dd * 0.8:
            drawdown_score = 9
        elif max_dd < peer_dd * 1.1:
            drawdown_score = 7
        elif max_dd < peer_dd * 1.3:
            drawdown_score = 5
        else:
            drawdown_score = 3

        # 4. 夏普比率 (0-10)
        sharpe_1y = perf_1y.get("sharpe_ratio", 0) or 0
        sharpe_annual = sharpe_1y if sharpe_1y else sharpe_3y
        if sharpe_annual > 1.5:
            sharpe_score = 10
        elif sharpe_annual > 1.0:
            sharpe_score = 8
        elif sharpe_annual > 0.5:
            sharpe_score = 6
        elif sharpe_annual > 0.3:
            sharpe_score = 4
        else:
            sharpe_score = 2

        # 5. 机构持有变化 (0-8)
        holders = fund.get("holders", None)
        import pandas as pd
        if holders is not None and not (hasattr(holders, "empty") and holders.empty):
            inst_score = 5
        else:
            inst_score = 4

        micro_total = min(50, manager_score + alpha_score + drawdown_score + sharpe_score + inst_score)
        return micro_total, details, ""
```

- [ ] **Step 5: Wire scorers into FundAnalyzer**

In `src/analysis/scorer.py`, import:
```python
from src.analysis.scoring import MacroScorer, MesoScorer, MicroScorer
```

In `FundAnalyzer.__init__`, add:
```python
self._macro = MacroScorer()
self._meso = MesoScorer()
self._micro = MicroScorer()
```

Replace `_score_macro`:
```python
def _score_macro(self, code: str) -> Tuple[int, Dict, str]:
    return self._macro.score(code, self.funds.get(code, {}))
```

Replace `_score_meso`:
```python
def _score_meso(self, code: str, completeness: str) -> Tuple[Optional[int], Dict, str]:
    return self._meso.score(code, self.funds.get(code, {}), completeness)
```

Replace `_score_micro`:
```python
def _score_micro(self, code: str) -> Tuple[int, Dict, str]:
    return self._micro.score(code, self.funds.get(code, {}))
```

Delete `_macro_basis`, `SECTOR_MAP` (unused in the scorers after extraction) from FundAnalyzer.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```
Expected: 89 passed

- [ ] **Step 7: Commit**

```bash
git add src/analysis/scoring/ src/analysis/scorer.py
git commit -m "refactor: extract Macro/Meso/MicroScorer from FundAnalyzer"
```

---

### Task 4: Create FactorMatrixBuilder

**Files:**
- Create: `src/analysis/factors.py`
- Modify: `src/analysis/scorer.py`

- [ ] **Step 1: Create `src/analysis/factors.py`**

```python
"""Factor matrix builder and score confidence calculator."""
from __future__ import annotations

from typing import Dict


class FactorMatrixBuilder:
    def build(self, score: dict, news_context: dict | None = None) -> dict:
        """Build an auditable factor matrix without changing the legacy score."""
        features = score.get("feature_matrix") or {}
        news_eval = (news_context or {}).get("news_evaluation") or {}
        catalyst = news_eval.get("overall_score")
        meso_score = score.get("meso_score")

        def factor(name, value, points, weight, source, missing_policy="neutral"):
            return {
                "name": name,
                "value": value,
                "score": points,
                "weight": weight,
                "source": source,
                "missing_policy": missing_policy,
            }

        macro = [
            factor(
                "fund_type_cycle_fit",
                score.get("fund_type", ""),
                round((score.get("macro_score") or 0) / 20, 4),
                0.20,
                "basic",
            )
        ]

        meso = []
        if meso_score is not None:
            meso.append(
                factor(
                    "sector_position",
                    meso_score,
                    round((meso_score or 0) / 30, 4),
                    0.18,
                    "rules",
                )
            )
        hhi_value = features.get("hhi_index")
        meso.append(
            factor(
                "hhi_index",
                hhi_value,
                self._score_hhi_factor(hhi_value),
                0.07,
                "holdings",
                "neutral_when_missing",
            )
        )
        if catalyst is not None:
            meso.append(
                factor(
                    "news_catalyst",
                    round(float(catalyst), 4),
                    round(max(-1.0, min(1.0, float(catalyst))), 4),
                    0.05,
                    "news_evaluation",
                    "ignore_when_missing",
                )
            )

        micro = [
            factor("sortino_ratio", features.get("sortino_ratio"), self._score_positive_ratio(features.get("sortino_ratio"), 1.5), 0.10, "feature_matrix"),
            factor("sharpe_1y", features.get("sharpe_1y"), self._score_positive_ratio(features.get("sharpe_1y"), 1.5), 0.10, "performance"),
            factor("max_drawdown_3y_pct", features.get("max_drawdown_3y_pct"), self._score_drawdown_factor(features.get("max_drawdown_3y_pct")), 0.10, "performance"),
            factor("annual_volatility", features.get("annual_volatility"), self._score_volatility_factor(features.get("annual_volatility")), 0.08, "performance"),
            factor("jensen_alpha", features.get("jensen_alpha"), self._score_positive_ratio(features.get("jensen_alpha"), 0.08), 0.06, "feature_matrix", "neutral_when_missing"),
            factor("information_ratio", features.get("information_ratio"), self._score_positive_ratio(features.get("information_ratio"), 0.8), 0.04, "feature_matrix", "neutral_when_missing"),
            factor("beta", features.get("beta"), self._score_beta_factor(features.get("beta")), 0.02, "feature_matrix", "neutral_when_missing"),
            factor("win_rate_1y", features.get("win_rate_1y"), self._score_positive_ratio(features.get("win_rate_1y"), 0.6), 0.05, "feature_matrix", "neutral_when_missing"),
            factor("calmar_ratio_1y", features.get("calmar_ratio_1y"), self._score_positive_ratio(features.get("calmar_ratio_1y"), 1.0), 0.05, "feature_matrix", "neutral_when_missing"),
        ]

        return {"macro": macro, "meso": meso, "micro": micro}

    def score_confidence(self, completeness: str, features: dict, factor_matrix: dict) -> float:
        base = {"A": 0.92, "B": 0.82, "C": 0.60, "D": 0.25}.get(completeness, 0.50)
        factors = [
            factor
            for dimension in (factor_matrix or {}).values()
            for factor in (dimension or [])
        ]
        if not factors:
            return round(base * 0.8, 2)
        available = sum(1 for f in factors if f.get("value") not in (None, ""))
        coverage = available / len(factors)
        key_metrics = ["max_drawdown_3y_pct", "annual_volatility", "sharpe_1y"]
        key_coverage = sum(1 for k in key_metrics if features.get(k) is not None) / len(key_metrics)
        confidence = base * (0.75 + 0.15 * coverage + 0.10 * key_coverage)
        return round(min(0.98, max(0.20, confidence)), 2)

    def _score_positive_ratio(self, value, good_threshold: float) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if good_threshold == 0:
            return 0.5
        return round(max(0.0, min(1.0, val / good_threshold)), 4)

    def _score_drawdown_factor(self, value) -> float:
        try:
            val = abs(float(value))
        except (TypeError, ValueError):
            return 0.5
        if val <= 10:
            return 1.0
        if val >= 35:
            return 0.1
        return round(1.0 - (val - 10) / 25 * 0.9, 4)

    def _score_volatility_factor(self, value) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if val <= 8:
            return 1.0
        if val >= 35:
            return 0.1
        return round(1.0 - (val - 8) / 27 * 0.9, 4)

    def _score_hhi_factor(self, value) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if val <= 1500:
            return 1.0
        if val >= 3500:
            return 0.2
        return round(1.0 - (val - 1500) / 2000 * 0.8, 4)

    def _score_beta_factor(self, value) -> float:
        try:
            val = abs(float(value))
        except (TypeError, ValueError):
            return 0.5
        return round(max(0.0, min(1.0, 1.0 - abs(val - 1.0) * 0.4)), 4)
```

- [ ] **Step 2: Wire FactorMatrixBuilder into FundAnalyzer**

In `src/analysis/scorer.py`, import:
```python
from src.analysis.factors import FactorMatrixBuilder
```

In `FundAnalyzer.__init__`, add:
```python
self._factors = FactorMatrixBuilder()
```

Replace `_build_factor_matrix`:
```python
def _build_factor_matrix(self, score: dict, news_context: dict = None) -> dict:
    return self._factors.build(score, news_context=news_context)
```

Replace `_score_confidence`:
```python
def _score_confidence(self, completeness: str, features: dict, factor_matrix: dict) -> float:
    return self._factors.score_confidence(completeness, features, factor_matrix)
```

Delete `_score_positive_ratio`, `_score_drawdown_factor`, `_score_volatility_factor`, `_score_hhi_factor`, `_score_beta_factor` from FundAnalyzer.

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```
Expected: 89 passed

- [ ] **Step 4: Commit**

```bash
git add src/analysis/factors.py src/analysis/scorer.py
git commit -m "refactor: extract FactorMatrixBuilder from FundAnalyzer"
```

---

### Task 5: Final cleanup — remove dead code from scorer.py

**Files:**
- Modify: `src/analysis/scorer.py`

- [ ] **Step 1: Clean up `src/analysis/scorer.py`**

Verify scorer.py now only contains:
- `FundAnalyzer.__init__` with all sub-objects
- `FundAnalyzer.load_fund` → delegates to `self._loader`
- `FundAnalyzer.score_fund` → uses all sub-objects
- `FundAnalyzer._score_macro/_score_meso/_score_micro` → delegates to sub-scorers
- `FundAnalyzer._compute_perf_from_nav` → delegates to `self._metrics`
- `FundAnalyzer._compute_advanced_metrics` → delegates to `self._metrics`
- `FundAnalyzer._build_factor_matrix` → delegates to `self._factors`
- `FundAnalyzer._score_confidence` → delegates to `self._factors`
- `FundAnalyzer._batch_factor_matrix` (if it exists)
- `FundAnalyzer._build_fund_context` + `build_agent_score_context`
- `FundAnalyzer._deduce_recommendation` + `_level_from_score`
- `FundAnalyzer.compute_correlations` + `stress_test`
- `FundAnalyzer.compute_correlations` + `stress_test`

Remove any leftover dead code. Ensure the following methods ARE NOT present in `FundAnalyzer`:
- `_score_positive_ratio`
- `_score_drawdown_factor`
- `_score_volatility_factor`
- `_score_hhi_factor`
- `_score_beta_factor`
- `_macro_basis`
- `SECTOR_MAP`

Ensure imports at top of `scorer.py` are clean:
```python
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

from src.analysis.factors import FactorMatrixBuilder
from src.analysis.holdings import compute_hhi
from src.analysis.loader import FundDataLoader
from src.analysis.metrics import MetricsCalculator
from src.analysis.scoring import MacroScorer, MesoScorer, MicroScorer
from src.config.defaults import QUANT_CONFIG, RISK_FREE_RATE
```

- [ ] **Step 2: Final test run**

```bash
python -m pytest tests/ -x --tb=short -q
```
Expected: 89 passed (no regressions, all assertions hold)

- [ ] **Step 3: Verify diagnose command works**

```bash
python -m src.cli diagnose 008253 2>&1 | head -30
```
Expected: Same output as before refactoring.

- [ ] **Step 4: Commit**

```bash
git add src/analysis/scorer.py
git commit -m "refactor: cleanup FundAnalyzer - remove extracted dead code"
```
