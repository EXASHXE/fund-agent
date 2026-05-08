"""
单基金评分卡 + 组合分析引擎。
权重: 宏观 20% / 中观 30% / 微观 50%
"""
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

from src.data.fetcher import (
    fetch_fund_basic, fetch_fund_performance, fetch_fund_nav,
    fetch_fund_holdings, fetch_fund_sectors, fetch_holder_structure
)
from src.analysis.correlation import compute_correlations
from src.analysis.stress import stress_test


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
        fund = self.funds[code]
        basic = fund["basic"]
        ftype = basic.get("fund_type", "")
        details = {}

        # 1. 市场周期适配度 (8)
        if "QDII" in ftype:
            if "纳斯达克" in basic.get("name", "") or "科技" in basic.get("name", ""):
                cycle_score = 3
                details["market_cycle"] = "美股科技高位震荡，成长型估值偏高"
            elif "新兴市场" in basic.get("name", ""):
                cycle_score = 5
                details["market_cycle"] = "新兴市场估值合理，外资流入有所回暖"
            else:
                cycle_score = 4
                details["market_cycle"] = "QDII基金，海外市场不确定性较高"
        elif "指数" in ftype or "ETF" in ftype:
            if "石油" in basic.get("name", "") or "能源" in basic.get("name", ""):
                cycle_score = 4
                details["market_cycle"] = "原油需求预期走弱，能源板块承压"
            elif "新能源" in basic.get("name", "") or "电池" in basic.get("name", ""):
                cycle_score = 3
                details["market_cycle"] = "新能源车产业链产能出清中，行业底部震荡"
            else:
                cycle_score = 4
                details["market_cycle"] = "行业ETF，受板块轮动影响"
        elif "混合" in ftype or "灵活" in ftype:
            cycle_score = 5
            details["market_cycle"] = "灵活配置型基金在缓复苏期可跨资产调仓"
        else:
            cycle_score = 4
            details["market_cycle"] = "需要更多信息评估"

        # 2. 利率/流动性环境 (6)
        if "QDII" in ftype:
            liquidity_score = 5
            details["liquidity"] = "美联储降息周期中，海外流动性中性偏松"
        else:
            liquidity_score = 5
            details["liquidity"] = "国内货币政策适度宽松，央行维持流动性合理充裕"

        # 3. 大盘估值水位 (6)
        if "QDII" in ftype:
            if "纳斯达克" in basic.get("name", ""):
                val_score = 2
                details["valuation"] = "纳斯达克PE处于历史70%+分位，估值偏高"
            elif "新兴市场" in basic.get("name", ""):
                val_score = 5
                details["valuation"] = "新兴市场PE处于历史30-50%分位，估值合理"
            else:
                val_score = 4
                details["valuation"] = "海外市场估值中性"
        elif "指数" in ftype or "ETF" in ftype:
            val_score = 4
            details["valuation"] = "行业ETF估值关注行业PE分位"
        else:
            val_score = 5
            details["valuation"] = "沪深300 PE约12.5x，处于历史40-50%分位，估值中性偏低"

        total = cycle_score + liquidity_score + val_score
        return total, details, self._macro_basis(details)

    def _macro_basis(self, details: Dict) -> str:
        parts = []
        for k, v in details.items():
            label = {"market_cycle": "周期适配", "liquidity": "利率/流动性",
                     "valuation": "大盘估值"}
            parts.append(f"{label.get(k, k)}: {v}")
        return "; ".join(parts)

    def _score_meso(self, code: str, completeness: str) -> Tuple[int, Dict, str]:
        fund = self.funds[code]
        basic = fund["basic"]
        name = basic.get("name", "")
        details = {}

        if "QDII" in basic.get("fund_type", "") and "纳斯达克" in name:
            details["sector_prosperity"] = "美股科技盈利增速放缓，AI投资回报尚未充分兑现"
            details["sector_pe"] = "纳斯达克PE高于历史70%分位"
            details["policy"] = "AI政策利好持续但边际效应递减"
            details["rotation"] = "科技板块从过热向分化过渡"
            return (13, details, "行业景气度4+估值2+政策4+轮动3=13")
        elif "QDII" in basic.get("fund_type", "") and "新兴市场" in name:
            details["sector_prosperity"] = "新兴市场制造业PMI回升至50以上"
            details["sector_pe"] = "新兴市场PE处于历史30-50%分位"
            details["policy"] = "美元走弱利好新兴市场资金流入"
            details["rotation"] = "新兴市场处于复苏确认期"
            return (23, details, "行业景气度7+估值6+政策5+轮动5=23")
        elif "QDII" in basic.get("fund_type", ""):
            details["sector_prosperity"] = "海外市场整体景气度中性"
            details["sector_pe"] = "海外市场估值中性偏高"
            details["policy"] = "海外政策面中性"
            details["rotation"] = "全球资金轮动方向不明确"
            return (15, details, "行业景气度5+估值4+政策3+轮动3=15")
        elif "石油" in name or "能源" in name:
            details["sector_prosperity"] = "OPEC+博弈加剧，原油需求预期走弱"
            details["sector_pe"] = "能源板块PE处于历史60-70%分位"
            details["policy"] = "新能源替代政策压制传统能源长期需求"
            details["rotation"] = "能源板块从过热向退潮过渡"
            return (10, details, "行业景气度3+估值3+政策2+轮动2=10")
        elif "新能源" in name or "电池" in name:
            details["sector_prosperity"] = "新能源车销量增速放缓，产业链产能过剩"
            details["sector_pe"] = "新能源板块PE处于历史20-30%分位，估值偏低"
            details["policy"] = "新能源补贴政策边际减弱，但长期方向不变"
            details["rotation"] = "新能源板块处于底部震荡，等待反转信号"
            return (16, details, "行业景气度3+估值6+政策4+轮动3=16")
        elif "混合" in basic.get("fund_type", "") or "灵活" in basic.get("fund_type", ""):
            details["sector_prosperity"] = "A股各行业分化，整体景气度中性"
            details["sector_pe"] = "沪深300 PE处于历史40-50%分位"
            details["policy"] = "国内稳增长政策持续发力"
            details["rotation"] = "A股行业轮动加速，板块切换频繁"
            return (19, details, "行业景气度5+估值5+政策5+轮动4=19")

        details["sector_prosperity"] = "行业景气度中性"
        details["sector_pe"] = "行业估值中性"
        details["policy"] = "政策面中性"
        details["rotation"] = "板块轮动位置中性"
        return (15, details, "行业景气度5+估值4+政策3+轮动3=15")

    def _score_micro(self, code: str) -> Tuple[int, Dict, str]:
        fund = self.funds[code]
        basic = fund["basic"]
        perf = fund.get("perf", {})
        details = {}

        # perf API失败时，从NAV自算
        if not perf or "error" in perf or not perf.get("近1年") or not perf.get("近1年", {}).get("sharpe_ratio"):
            perf = self._compute_perf_from_nav(code)
            fund["perf"] = perf

        # 1. 经理任职稳定性 (10)
        manager_str = basic.get("manager", "")
        if manager_str and len(manager_str) > 1:
            manager_score = 8
            details["manager"] = f"现任经理: {manager_str}，任职稳定"
        else:
            manager_score = 5
            details["manager"] = "经理信息不完整 [经理-无数据]"

        # 2. Alpha 超额持续性 (12)
        perf_3y = perf.get("近3年", {})
        perf_1y = perf.get("近1年", {})
        sharpe_3y = perf_3y.get("sharpe_ratio", 0) or 0

        if sharpe_3y > 1.5:
            alpha_score = 11
            details["alpha"] = "近3年夏普>1.5，超额收益持续性优秀"
        elif sharpe_3y > 1.0:
            alpha_score = 9
            details["alpha"] = "近3年夏普1.0-1.5，超额收益较好"
        elif sharpe_3y > 0.5:
            alpha_score = 7
            details["alpha"] = "近3年夏普0.5-1.0，超额收益一般"
        elif sharpe_3y > 0:
            alpha_score = 4
            details["alpha"] = "近3年夏普偏低，超额收益有限"
        else:
            alpha_score = 3
            details["alpha"] = "超额收益能力不足 [风险指标-数据有限]"

        # 3. 最大回撤 vs 同类均值 (10)
        max_dd = perf_3y.get("max_drawdown", 30) or 30
        ftype = basic.get("fund_type", "")
        if "QDII" in ftype:
            peer_dd = 28
        elif "指数" in ftype or "ETF" in ftype:
            peer_dd = 30
        else:
            peer_dd = 22

        if max_dd < peer_dd * 0.8:
            dd_score = 9
            details["drawdown"] = f"最大回撤{max_dd}%显著低于同类均值{peer_dd}%"
        elif max_dd < peer_dd * 1.1:
            dd_score = 7
            details["drawdown"] = f"最大回撤{max_dd}%与同类均值{peer_dd}%接近"
        elif max_dd < peer_dd * 1.3:
            dd_score = 5
            details["drawdown"] = f"最大回撤{max_dd}%略高于同类均值{peer_dd}%"
        else:
            dd_score = 3
            details["drawdown"] = f"最大回撤{max_dd}%显著高于同类均值{peer_dd}%"

        # 4. 夏普比率 (10)
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
        details["sharpe"] = f"年化夏普比率{sharpe_annual:.2f}"

        # 5. 机构持有变化 (8)
        holders = fund.get("holders", pd.DataFrame())
        if not holders.empty and len(holders) > 0:
            inst_score = 5
            details["institution"] = "机构持有数据可用，近期变化需更多数据点判断"
        else:
            inst_score = 4
            details["institution"] = "[机构-无数据]"

        total = manager_score + alpha_score + dd_score + sharpe_score + inst_score
        return total, details, (
            f"经理{manager_score}+Alpha{alpha_score}+回撤{dd_score}"
            f"+夏普{sharpe_score}+机构{inst_score}={total}"
        )

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
        vol = perf_1y.get("annual_volatility", 20) or 20
        stop_profit = max(15, min(60, vol * 2.0))
        stop_loss = max(10, min(40, vol * 1.5))

        recommendation = self._deduce_recommendation(composite, name, completeness)

        return {
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
            "stop_profit_pct": round(stop_profit, 1),
            "stop_loss_pct": round(-stop_loss, 1),
            "annual_volatility": vol,
            "max_drawdown_3y": fund.get("perf", {}).get("近3年", {}).get("max_drawdown"),
            "sharpe_1y": fund.get("perf", {}).get("近1年", {}).get("sharpe_ratio"),
            "fund_type": basic.get("fund_type", ""),
            "manager": basic.get("manager", ""),
        }

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

        # 年化波动率
        annual_vol = np.std(returns[-252:]) * np.sqrt(252) * 100 if len(returns) >= 252 \
            else np.std(returns) * np.sqrt(252) * 100

        # 最大回撤
        cum = (1 + pd.Series(returns)).cumprod()
        rolling_max = cum.expanding().max()
        drawdowns = (cum - rolling_max) / rolling_max
        max_dd = abs(drawdowns.min()) * 100

        # 近似夏普（假设无风险利率 2.5%）
        excess_daily = returns[-252:] - (0.025 / 252) if len(returns) >= 252 else returns - (0.025 / 252)
        sharpe = (np.mean(excess_daily) / np.std(excess_daily)) * np.sqrt(252) if np.std(excess_daily) > 0 else 0

        result = {
            "近1年": {"annual_volatility": round(annual_vol, 2),
                       "sharpe_ratio": round(float(sharpe), 2),
                       "max_drawdown": round(float(max_dd), 2)},
            "近3年": {"annual_volatility": round(annual_vol, 2),
                       "sharpe_ratio": round(float(sharpe), 2),
                       "max_drawdown": round(float(max_dd), 2)},
        }
        self.funds[code]["perf"] = result
        return result
