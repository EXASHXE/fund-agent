"""
单基金评分卡 + 组合分析引擎。
权重: 宏观 20% / 中观 30% / 微观 50%
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure
)
from src.analysis.correlation import compute_correlations
from src.analysis.stress import stress_test
from src.analysis.holdings import compute_hhi
from src.analysis.metrics import MetricsCalculator



class FundAnalyzer:
    """单基金评分卡 + 组合分析"""

    SECTOR_MAP = {
        "信息技术": "Technology", "通信": "Telecom", "医疗": "Healthcare",
        "医药": "Healthcare", "金融": "Finance", "消费": "Consumer",
        "新能源": "New Energy", "能源": "Energy", "原材料": "Materials",
        "工业": "Industrial", "房地产": "Real Estate", "公用事业": "Utilities",
        "石油": "Oil", "天然气": "Natural Gas", "银行": "Banking",
        "保险": "Insurance", "证券": "Securities", "汽车": "Automobile",
        "电池": "Battery", "电子": "Electronics", "半导体": "Semiconductor",
        "互联网": "Internet", "传媒": "Media",
    }

    def __init__(self):
        self.funds = {}
        self._metrics = MetricsCalculator()

    def load_fund(self, code: str):
        """采集单基金全部数据"""
        print(f"  [Layer 1] 采集 {code} 数据...")
        basic = fetch_fund_basic(code)
        perf = fetch_fund_performance(code)
        nav = fetch_fund_nav(code)
        holdings = fetch_fund_holdings(code)
        sectors = fetch_fund_sectors(code)
        holders = fetch_holder_structure(code)

        self.funds[code] = {
            "basic": basic,
            "perf": perf,
            "nav": nav,
            "holdings": holdings,
            "sectors": sectors,
            "holders": holders,
        }

        completeness = self._assess_completeness(basic, perf, nav, holdings, sectors)
        self.funds[code]["completeness"] = completeness
        print(f"    完整度: {completeness}")
        return completeness

    def _assess_completeness(self, basic, perf, nav, holdings, sectors) -> str:
        has_basic = bool(basic) and "error" not in basic
        has_nav = isinstance(nav, pd.DataFrame) and len(nav) > 30
        has_perf = bool(perf) and "error" not in perf

        if not has_basic or not has_nav:
            return "D"

        core_ok = has_basic and has_nav  # perf可从NAV估算
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
            return "B"  # 有NAV+增强数据，但perf缺失
        if core_ok:
            return "C"
        return "D"

    def _score_macro(self, code: str) -> Tuple[int, Dict, str]:
        fund = self.funds.get(code, {})
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

    def _macro_basis(self, details: Dict) -> str:
        parts = []
        for k, v in details.items():
            label = {"market_cycle": "周期适配", "liquidity": "利率/流动性",
                     "valuation": "大盘估值"}
            parts.append(f"{label.get(k, k)}: {v}")
        return "; ".join(parts)

    def _score_meso(self, code: str, completeness: str) -> Tuple[Optional[int], Dict, str]:
        if completeness in ("C", "D"):
            return None, {}, ""

        fund = self.funds.get(code, {})
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

    def _score_micro(self, code: str) -> Tuple[int, Dict, str]:
        fund = self.funds[code]
        basic = fund["basic"]
        perf = fund.get("perf", {})
        details = {}

        # perf API失败时，从NAV自算
        if not perf or "error" in perf or not perf.get("近1年") or not perf.get("近1年", {}).get("sharpe_ratio"):
            perf = self._compute_perf_from_nav(code)
            fund["perf"] = perf

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
        holders = fund.get("holders", pd.DataFrame())
        if not holders.empty and len(holders) > 0:
            inst_score = 5
        else:
            inst_score = 4

        micro_total = min(50, manager_score + alpha_score + drawdown_score + sharpe_score + inst_score)
        return micro_total, details, ""

    def score_fund(self, code: str, news_context: Dict = None) -> Dict:
        fund = self.funds[code]
        if news_context is not None:
            fund["news_context"] = news_context
        basic = fund["basic"]
        completeness = fund["completeness"]
        name = basic.get("name", code)

        macro_total, macro_detail, macro_basis = self._score_macro(code)
        meso_total, meso_detail, meso_basis = self._score_meso(code, completeness)
        micro_total, micro_detail, micro_basis = self._score_micro(code)

        if completeness in ("C", "D"):
            composite = macro_total + micro_total
            composite = int(round(composite / 70 * 100))
            meso_total = None
        else:
            composite = macro_total + meso_total + micro_total

        if composite >= 75:
            level, emoji, tendency = "green", "🟢", "维持或加仓"
        elif composite >= 50:
            level, emoji, tendency = "yellow", "🟡", "持有观察，可继续定投"
        elif composite >= 30:
            level, emoji, tendency = "orange", "🟠", "减仓或暂停定投"
        else:
            level, emoji, tendency = "red", "🔴", "止盈/止损离场"

        perf_1y = fund.get("perf", {}).get("近1年", {})
        vol = round(perf_1y.get("annual_volatility", 20) or 20, 2)
        stop_profit = max(15, min(60, vol * 2.0))
        stop_loss = max(10, min(40, vol * 1.5))
        max_dd_3y = fund.get("perf", {}).get("近3年", {}).get("max_drawdown")
        sharpe_1y = fund.get("perf", {}).get("近1年", {}).get("sharpe_ratio")

        recommendation = self._deduce_recommendation(composite, name, completeness)

        sortino_val = 0.0
        nav_df = fund.get("nav")
        if isinstance(nav_df, pd.DataFrame) and not nav_df.empty and "日增长率" in nav_df.columns:
            daily_returns = nav_df["日增长率"].dropna().values / 100.0
            if len(daily_returns) >= 20:
                sortino_val = self._metrics.sortino_ratio(daily_returns.tolist())

        hhi_val = 0.0
        funds_holdings = fund.get("holdings", pd.DataFrame())
        if isinstance(funds_holdings, pd.DataFrame) and not funds_holdings.empty:
            hhi_val = compute_hhi(funds_holdings) or 0.0

        nav_df = fund.get("nav")
        adv = self._metrics.advanced_metrics(nav_df, basic) if completeness in ("A", "B") else {}
        alpha_val = adv.get("jensen_alpha", 0.0) if adv else 0.0
        ir_val = adv.get("information_ratio", 0.0) if adv else 0.0
        beta_val = adv.get("beta", 1.0) if adv else 1.0
        win_rate_val = adv.get("win_rate_1y", 0.0) if adv else 0.0
        calmar_val = adv.get("calmar_ratio_1y", 0.0) if adv else 0.0

        score = {
            "fund_code": code,
            "fund_name": name,
            "data_completeness": completeness,
            "composite_score": composite,
            "score_level": level,
            "score_level_emoji": emoji,
            "score_tendency": tendency,
            "macro_score": macro_total,
            "macro_basis": macro_basis,
            "macro_detail": macro_detail,
            "meso_score": meso_total,
            "meso_basis": meso_basis,
            "meso_detail": meso_detail,
            "micro_score": micro_total,
            "micro_basis": micro_basis,
            "micro_detail": micro_detail,
            "recommendation": recommendation["label"],
            "action_logic": recommendation["logic"],
            "stop_profit_pct": round(stop_profit, 2),
            "stop_loss_pct": round(-stop_loss, 2),
            "annual_volatility": vol,
            "max_drawdown_3y": round(max_dd_3y, 2) if max_dd_3y is not None else None,
            "sharpe_1y": round(sharpe_1y, 2) if sharpe_1y is not None else None,
            "fund_type": basic.get("fund_type", ""),
            "manager": basic.get("manager", ""),
            "scoring_matrix": {
                "quant_baseline": {
                    "macro_score": int(macro_total),
                    "meso_score": int(meso_total) if meso_total is not None else None,
                    "micro_score": int(micro_total),
                    "total_baseline_score": int(composite),
                },
                "agent_overlay": {
                    "macro_adjustment": 0,
                    "meso_adjustment": 0,
                    "micro_adjustment": 0,
                    "total_adjustment": 0,
                    "overlay_rationale": "",
                },
                "final_score": int(composite),
                "score_tendency": tendency,
            },
            "feature_matrix": {
                "hhi_index": hhi_val,
                "jensen_alpha": round(float(alpha_val), 4),
                "sortino_ratio": sortino_val,
                "information_ratio": round(float(ir_val), 4),
                "beta": round(float(beta_val), 4),
                "win_rate_1y": round(float(win_rate_val), 2),
                "calmar_ratio_1y": round(float(calmar_val), 2),
                "max_drawdown_3y_pct": round(float(max_dd_3y), 2) if max_dd_3y else None,
                "annual_volatility": round(float(vol), 2),
                "sharpe_1y": round(float(sharpe_1y), 2) if sharpe_1y else None,
            },
        }
        score["factor_matrix"] = self._build_factor_matrix(
            score,
            news_context=fund.get("news_context", {}),
        )
        score["score_confidence"] = self._score_confidence(
            completeness,
            score["feature_matrix"],
            score["factor_matrix"],
        )
        score["scoring_matrix"]["final_confidence"] = score["score_confidence"]
        score["score_source"] = "rules_seed"
        score["agent_review_required"] = True
        score["agent_score_context"] = self.build_agent_score_context(code, score)
        return score

    def _build_factor_matrix(self, score: Dict, news_context: Dict = None) -> Dict:
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

    def _score_confidence(self, completeness: str, features: Dict, factor_matrix: Dict) -> float:
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

    def _deduce_recommendation(self, score: int, name: str,
                                completeness: str) -> Dict:
        if completeness == "D":
            return {
                "label": "数据不足",
                "logic": "核心数据缺失，无法给出可靠建议。[数据缺失-无法评估]"
            }
        if score >= 75:
            return {
                "label": "买入 / 逢低加仓",
                "logic": f"综合评分{score}分，处于优质区间。建议维持现有仓位，回调时逢低加仓。注意控制单一基金仓位不超过总资产15%。"
            }
        elif score >= 60:
            return {
                "label": "持有 / 继续定投",
                "logic": f"综合评分{score}分，处于中上区间。基金质地尚可，建议继续持有并维持当前定投策略。"
            }
        elif score >= 45:
            return {
                "label": "持有观察",
                "logic": f"综合评分{score}分，处于中性偏弱区间。建议暂持但暂停新增定投，密切关注评分变化。若下次评分再降>15分可考虑减仓。"
            }
        elif score >= 30:
            return {
                "label": "减仓 / 暂停定投",
                "logic": f"综合评分{score}分，处于偏弱区间。建议暂停定投，分批减仓30-50%，保留部分仓位观察。"
            }
        else:
            return {
                "label": "止损离场",
                "logic": f"综合评分{score}分，处于危险区间。建议尽快止损离场，将资金配置到评分≥75的优质标的上。"
            }

    def build_agent_score_context(self, code: str, rule_score: Dict) -> Dict:
        """构造 agent 自主评分需要的证据包。"""
        from src.news.agent_context import build_score_judgment_context

        return build_score_judgment_context(
            fund_context=self._build_fund_context(code),
            rule_score={k: v for k, v in rule_score.items() if k != "agent_score_context"},
        )

    def _build_fund_context(self, code: str) -> Dict:
        fund = self.funds.get(code, {})
        nav_df = fund.get("nav")
        nav_summary = {}
        if isinstance(nav_df, pd.DataFrame) and not nav_df.empty:
            returns = nav_df["日增长率"].dropna() if "日增长率" in nav_df.columns else pd.Series(dtype=float)
            nav_summary = {
                "rows": len(nav_df),
                "start": str(nav_df.index.min()),
                "end": str(nav_df.index.max()),
                "latest_nav": float(nav_df["单位净值"].iloc[-1]) if "单位净值" in nav_df.columns else None,
                "return_mean": round(float(returns.tail(60).mean()), 4) if not returns.empty else None,
                "return_std": round(float(returns.tail(60).std()), 4) if len(returns) > 1 else None,
            }
        holdings = fund.get("holdings")
        holding_rows = []
        if isinstance(holdings, pd.DataFrame) and not holdings.empty:
            for _, row in holdings.head(10).iterrows():
                holding_rows.append({k: row.get(k) for k in list(row.index)[:6]})
        sectors = fund.get("sectors")
        sector_rows = []
        if isinstance(sectors, pd.DataFrame) and not sectors.empty:
            for _, row in sectors.head(10).iterrows():
                sector_rows.append({k: row.get(k) for k in list(row.index)[:6]})
        hhi_val = None
        if isinstance(holdings, pd.DataFrame) and not holdings.empty:
            hhi_val = compute_hhi(holdings)
        return {
            "code": code,
            "basic": fund.get("basic", {}),
            "performance": fund.get("perf", {}),
            "data_completeness": fund.get("completeness"),
            "nav_summary": nav_summary,
            "top_holdings": holding_rows,
            "sectors": sector_rows,
            "hhi": hhi_val,
            "advanced_metrics": self._compute_advanced_metrics(code),
            "news_context": fund.get("news_context", {}),
        }

    def _level_from_score(self, composite: int) -> Tuple[str, str, str]:
        if composite >= 75:
            return "green", "🟢", "维持或加仓"
        if composite >= 50:
            return "yellow", "🟡", "持有观察，可继续定投"
        if composite >= 30:
            return "orange", "🟠", "减仓或暂停定投"
        return "red", "🔴", "止盈/止损离场"

    def compute_correlations(self):
        return compute_correlations(self.funds)

    def stress_test(self):
        return stress_test(self.funds)

    def _compute_perf_from_nav(self, code: str) -> dict:
        nav_df = self.funds[code].get("nav")
        result = self._metrics.compute_perf_from_nav(nav_df)
        self.funds[code]["perf"] = result
        return result

    def _compute_advanced_metrics(self, code: str) -> dict:
        fund = self.funds.get(code, {})
        nav_df = fund.get("nav")
        basic = fund.get("basic", {})
        return self._metrics.advanced_metrics(nav_df, basic)
