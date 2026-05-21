"""
单基金评分卡 + 组合分析引擎。
权重: 宏观 20% / 中观 30% / 微观 50%
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure
)
from src.analysis.correlation import compute_correlations
from src.analysis.stress import stress_test
from src.analysis.holdings import compute_hhi
from src.config.defaults import QUANT_CONFIG, RISK_FREE_RATE


def _compute_sortino_ratio(daily_returns: list, mar_annual: float = None) -> float:
    """计算索提诺比率（Sortino Ratio）

    Sortino = (Mean(R_i - MAR_daily) * 252) / DownsideDeviation_annual
    DownsideDeviation_annual = sqrt(mean(min(0, R_i - MAR_daily)^2)) * sqrt(252)

    仅惩罚下行波动，上行波动不计入风险。
    """
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


def _compute_hhi(holdings: list) -> float:
    """计算赫芬达尔-赫希曼指数（HHI）

    HHI = sum(weight_i^2) * 10000, range [0, 10000]
    > 2500: 高度集中 | 1500-2500: 中度集中 | < 1500: 分散
    """
    if not holdings:
        return 0.0

    weights = []
    for h in holdings:
        w = h.get("weight", 0) or h.get("ratio", 0) or h.get("proportion", 0) or 0
        weights.append(float(w))

    if not weights or sum(weights) == 0:
        return 0.0

    total = sum(weights)
    normalized = [w / total for w in weights]
    hhi = sum(w * w for w in normalized) * 10000
    return round(float(hhi), 2)


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

    def score_fund(self, code: str) -> Dict:
        fund = self.funds[code]
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

        # 计算 Sortino 比率（从净值日收益率）
        sortino_val = 0.0
        nav_df = fund.get("nav")
        if isinstance(nav_df, pd.DataFrame) and not nav_df.empty and "日增长率" in nav_df.columns:
            daily_returns = nav_df["日增长率"].dropna().values / 100.0
            if len(daily_returns) >= 20:
                sortino_val = _compute_sortino_ratio(daily_returns.tolist())

        # 计算 HHI
        hhi_val = 0.0
        funds_holdings = fund.get("holdings", pd.DataFrame())
        if isinstance(funds_holdings, pd.DataFrame) and not funds_holdings.empty:
            weight_col = None
            for col in ["占净值比例", "持仓占比", "占比", "持股占比"]:
                if col in funds_holdings.columns:
                    weight_col = col
                    break
            if weight_col:
                raw_weights = []
                for _, row in funds_holdings.head(10).iterrows():
                    try:
                        raw_weights.append(float(str(row[weight_col]).replace("%", "")))
                    except (ValueError, TypeError):
                        pass
                if raw_weights:
                    hhi_val = _compute_hhi([{"weight": w} for w in raw_weights])

        # 获取高级指标
        adv = self._compute_advanced_metrics(code) if completeness in ("A", "B") else {}
        alpha_val = adv.get("jensen_alpha", 0.0) if adv else 0.0
        ir_val = adv.get("information_ratio", 0.0) if adv else 0.0
        beta_val = adv.get("beta", 1.0) if adv else 1.0

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
                "max_drawdown_3y_pct": round(float(max_dd_3y), 2) if max_dd_3y else None,
                "annual_volatility": round(float(vol), 2),
                "sharpe_1y": round(float(sharpe_1y), 2) if sharpe_1y else None,
            },
        }
        score["score_source"] = "rules_seed"
        score["agent_review_required"] = True
        score["agent_score_context"] = self.build_agent_score_context(code, score)
        return score

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
        """
        从净值数据自算波动率/最大回撤/夏普比率（perf API 失败时的降级方案）。

        当前 AKShare 的 fund_individual_analysis_xq 对部分新成立基金（如 ETF 联接、
        指数基金 C 类份额）返回 'index_data_list' KeyError，这些基金有净值历史但无
        预先计算的绩效指标。本方法按以下公式从日频净值自算：

        - 年化波动率 = std(日收益率) × sqrt(252) × 100
        - 最大回撤 = 累计收益曲线中的最大峰值到谷值跌幅
        - 夏普比率 ≈ (日超额收益均值 / 日超额收益标准差) × sqrt(252)
          假定无风险利率 2.5%

        数据源评估：
        - AKShare: 覆盖 A 股/港股基金主力数据源，稳定性可接受
        - tushare: 需要 token，专业版收费；暂不作为备选
        - 东财/天天基金网页: 结构不稳定，频繁变更，维护成本高
        - 来自 NAV 自算是最可靠的降级方案，无需额外数据源

        当前不需额外数据源。若未来需要更多指标（如 Alpha/Beta/信息比率），
        可用指数基准（沪深300/纳斯达克100）回归计算。
        """
        import numpy as np

        nav_df = self.funds[code].get("nav")
        if nav_df is None or nav_df.empty or "日增长率" not in nav_df.columns:
            return {"近1年": {}, "近3年": {}}

        returns = nav_df["日增长率"].dropna().values / 100.0
        if len(returns) < 30:
            return {"近1年": {}, "近3年": {}}

        # 近1年指标（最后 252 个交易日）
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

        # 近3年指标（全量数据）
        vol_3y = np.std(returns) * np.sqrt(252) * 100
        excess_3y = returns - (0.025 / 252)
        sharpe_3y = (np.mean(excess_3y) / np.std(excess_3y)) * np.sqrt(252) if np.std(excess_3y) > 0 else 0
        cum_all = (1 + pd.Series(returns)).cumprod()
        rolling_max_all = cum_all.expanding().max()
        dd_3y = abs(((cum_all - rolling_max_all) / rolling_max_all).min()) * 100 if len(cum_all) > 0 else 0

        result = {
            "近1年": {"annual_volatility": round(vol_1y, 2),
                       "sharpe_ratio": round(float(sharpe_1y), 2),
                       "max_drawdown": round(float(dd_1y), 2)},
            "近3年": {"annual_volatility": round(vol_3y, 2),
                       "sharpe_ratio": round(float(sharpe_3y), 2),
                       "max_drawdown": round(float(dd_3y), 2)},
        }
        self.funds[code]["perf"] = result
        return result

    def _compute_advanced_metrics(self, code: str) -> dict:
        """计算信息比率、詹森 Alpha、特雷诺比率。

        基准: QDII 用纳斯达克 (.IXIC)，国内用沪深300 (sh000300)。
        无风险利率: 2.5%。
        """
        import numpy as np

        nav_df = self.funds[code].get("nav")
        if nav_df is None or nav_df.empty or "日增长率" not in nav_df.columns:
            return {}

        returns = nav_df["日增长率"].dropna().values / 100.0
        if len(returns) < 60:
            return {}

        basic = self.funds[code].get("basic", {})
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

        return {
            "information_ratio": round(float(ir), 4),
            "jensen_alpha": round(float(alpha), 4),
            "treynor_ratio": round(float(treynor), 4),
            "beta": round(float(beta), 4),
        }
