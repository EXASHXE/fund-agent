"""
高层存储 API — 供 Agent 调用的简洁接口。

典型用法:
    from src.db.storage import FundStorage

    store = FundStorage()

    # 1. 存入基金基础信息
    store.save_fund(code="008253", name="华宝致远混合(QDII)A", is_holding=True)

    # 2. 存入净值历史
    store.save_nav_bulk("008253", [{"date": d, "nav": n} ...])

    # 3. 存入一次完整分析快照
    store.save_analysis({
        "market_summary": "当前市场处于...",
        "scores": [
            {"fund_code": "008253", "composite_score": 68, "recommendation": "持有", ...},
        ],
        "recommendations": [...],
        "stress_tests": [...],
        "correlations": [...],
    })

    # 4. 查询历史分析
    snapshots = store.get_history(limit=10)
"""
import json
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .database import get_session, init_db
from .models import AnalysisSnapshot
from . import database as db
from src.config.shared import now as _shared_now

# 自定义 JSON 编码器，处理 date/datetime
class _JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class FundStorage:
    """基金数据持久化存储"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        init_db(db_path)

    @contextmanager
    def _session(self):
        session = get_session(self.db_path)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ================================================================
    #  基金基础信息
    # ================================================================

    def save_fund(self, code: str, name: str = None, fund_type: str = None,
                  is_holding: bool = False, is_watching: bool = False,
                  watch_reason: str = None, **kwargs) -> Dict:
        """保存/更新基金基本信息，返回 fund 字典"""
        with self._session() as s:
            fund = db.upsert_fund(s, code,
                                  name=name,
                                  fund_type=fund_type,
                                  is_holding=is_holding,
                                  is_watching=is_watching,
                                  watch_reason=watch_reason,
                                  **kwargs)
            return self._fund_to_dict(fund)

    def get_fund(self, code: str) -> Optional[Dict]:
        with self._session() as s:
            f = db.get_fund(s, code)
            return self._fund_to_dict(f) if f else None

    def list_holding_funds(self) -> List[Dict]:
        with self._session() as s:
            return [self._fund_to_dict(f) for f in db.get_holding_funds(s)]

    def list_watching_funds(self) -> List[Dict]:
        with self._session() as s:
            return [self._fund_to_dict(f) for f in db.get_watching_funds(s)]

    def list_all_funds(self) -> List[Dict]:
        with self._session() as s:
            return [self._fund_to_dict(f) for f in db.get_all_funds(s)]

    # ================================================================
    #  持仓/定投
    # ================================================================

    def save_holding(self, fund_code: str, buy_date: date, amount: float,
                     nav: float = None, shares: float = None,
                     after_1500: bool = False):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code, is_holding=True)
                s.flush()
            # 去重：相同 fund_id + buy_date + amount 不重复插入
            if not db.holding_exists(s, fund.id, buy_date, amount):
                db.add_holding(s, fund.id, buy_date, amount, nav, shares, after_1500)

    def save_dca(self, fund_code: str, frequency: str, amount: float,
                 next_date: date = None, is_active: bool = True):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code, is_holding=True)
                s.flush()
            db.upsert_dca(s, fund.id,
                          frequency=frequency,
                          amount=amount,
                          next_date=next_date,
                          is_active=is_active)

    # ================================================================
    #  净值 / 绩效 / 持仓明细
    # ================================================================

    def save_nav_bulk(self, fund_code: str, records: List[Dict[str, Any]]):
        """批量写入净值，records = [{"date": date, "nav": float, ...}]"""
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code)
                s.flush()
            db.bulk_insert_nav(s, fund.id, records)

    def save_performance(self, fund_code: str, calc_date: date,
                         period: str = "1y", **metrics):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code)
                s.flush()
            db.upsert_performance(s, fund.id, calc_date, period, **metrics)

    def save_top_holdings(self, fund_code: str, report_date: date,
                          holdings: List[Dict[str, Any]]):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code)
                s.flush()
            db.replace_top_holdings(s, fund.id, report_date, holdings)

    def save_sectors(self, fund_code: str, report_date: date,
                     sectors: List[Dict[str, Any]]):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code)
                s.flush()
            db.replace_sectors(s, fund.id, report_date, sectors)

    def save_holders(self, fund_code: str, report_date: date,
                     holder_data: Dict[str, Any]):
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                fund = db.upsert_fund(s, fund_code)
                s.flush()
            db.replace_holders(s, fund.id, report_date, holder_data)

    # ================================================================
    #  分析快照 — 核心导出接口
    # ================================================================

    def save_analysis(self, analysis: Dict[str, Any]) -> int:
        """
        保存一次完整分析结果。

        analysis 结构:
        {
            "analysis_date": datetime,       # 默认 now
            "market_summary": str,
            "portfolio_total_value": float,
            "portfolio_total_cost": float,
            "cash_ratio_pct": float,
            "scores": [                       # 单基金评分表
                {
                    "fund_code": str,
                    "data_completeness": "A"|"B"|"C"|"D",
                    "composite_score": int,
                    "score_level": "green"|"yellow"|"orange"|"red",
                    "macro_score": int, "macro_basis": str,
                    "meso_score": int, "meso_basis": str,
                    "micro_score": int, "micro_basis": str,
                    "macro_detail": dict, "meso_detail": dict, "micro_detail": dict,
                    "recommendation": str,
                    "current_position_pct": float,
                    "target_position_pct": float,
                    "dca_amount": float, "dca_frequency": str,
                    "stop_profit_pct": float, "stop_loss_pct": float,
                    "action_logic": str, "key_metrics": str,
                }
            ],
            "recommendations": [              # 推荐基金
                {
                    "fund_code": str, "fund_name": str,
                    "rec_type": "short"|"long",
                    "rec_logic": str,
                    "target_return_pct": float,
                    "stop_loss_pct": float,
                    "pearson_r": float,
                    "hold_period_days": int,          # short
                    "complementarity": str,            # long
                    "alternative_plan": str,           # long
                    "expected_annual_return": str,     # long
                    "is_added_to_watchlist": bool,
                }
            ],
            "stress_tests": [
                {"scenario_id": "S1", "scenario_desc": str,
                 "fund_code": str (optional),
                 "estimated_drawdown_pct": float,
                 "portfolio_drawdown_pct": float,
                 "impact_amount": float}
            ],
            "correlations": [
                {"fund_code_1": str, "fund_code_2": str,
                 "pearson_r": float, "is_warning": bool}
            ],
            "sector_concentrations": [
                {"sector_name": str, "total_weight_pct": float, "is_warning": bool}
            ],
        }
        返回 snapshot_id
        """
        with self._session() as s:
            snapshot = db.create_snapshot(
                s,
                analysis_date=analysis.get("analysis_date", _shared_now()),
                market_summary=analysis.get("market_summary"),
                portfolio_total_value=analysis.get("portfolio_total_value"),
                portfolio_total_cost=analysis.get("portfolio_total_cost"),
                cash_ratio_pct=analysis.get("cash_ratio_pct"),
            )

            # 评分
            for score_data in analysis.get("scores", []):
                fund_code = score_data.pop("fund_code", None)
                fund_id = None
                if fund_code:
                    fund = db.get_fund(s, fund_code)
                    if not fund:
                        fund = db.upsert_fund(s, fund_code)
                        s.flush()
                    fund_id = fund.id
                db.add_score(s, snapshot.id, fund_id, **score_data)

            # 推荐
            for rec_data in analysis.get("recommendations", []):
                db.add_recommendation(s, snapshot.id, **rec_data)

            # 压力测试
            stress = analysis.get("stress_tests", [])
            for st in stress:
                fund_code = st.pop("fund_code", None)
                fund_id = None
                if fund_code:
                    fund = db.get_fund(s, fund_code)
                    fund_id = fund.id if fund else None
                # 恢复 fund_code 以便后续使用
                if fund_code:
                    st["fund_id"] = fund_id
            db.add_stress_tests(s, snapshot.id, stress)

            # 相关性矩阵
            cors = analysis.get("correlations", [])
            for c in cors:
                fc1 = c.pop("fund_code_1", None)
                fc2 = c.pop("fund_code_2", None)
                f1 = db.get_fund(s, fc1) if fc1 else None
                f2 = db.get_fund(s, fc2) if fc2 else None
                c["fund_id_1"] = f1.id if f1 else None
                c["fund_id_2"] = f2.id if f2 else None
            db.add_correlations(s, snapshot.id, cors)

            # 行业集中度
            db.add_sector_concentrations(
                s, snapshot.id, analysis.get("sector_concentrations", [])
            )

            s.commit()
            return snapshot.id

    def load_analysis(self, snapshot_id: int) -> Optional[Dict]:
        """加载一次完整分析结果"""
        with self._session() as s:
            snap = s.get(AnalysisSnapshot, snapshot_id)
            if not snap:
                return None
            return self._build_analysis_dict(snap)

    def get_latest_analysis(self) -> Optional[Dict]:
        """加载最近一次分析"""
        with self._session() as s:
            snap = db.get_latest_snapshot(s)
            if not snap:
                return None
            return self._build_analysis_dict(snap)

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取历史分析摘要列表"""
        with self._session() as s:
            snapshots = db.get_snapshots(s, limit)
            return [self._snapshot_summary(snap) for snap in snapshots]

    def get_fund_score_history(self, fund_code: str, limit: int = 10) -> List[Dict]:
        """获取某基金的历史评分趋势"""
        with self._session() as s:
            fund = db.get_fund(s, fund_code)
            if not fund:
                return []
            scores = db.get_fund_score_history(s, fund.id, limit)
            return [{
                "analysis_date": fs.snapshot.analysis_date.isoformat()
                if fs.snapshot else None,
                "composite_score": fs.composite_score,
                "score_level": fs.score_level,
                "recommendation": fs.recommendation,
                "stop_profit_pct": fs.stop_profit_pct,
                "stop_loss_pct": fs.stop_loss_pct,
                "macro_score": fs.macro_score,
                "meso_score": fs.meso_score,
                "micro_score": fs.micro_score,
            } for fs in scores]

    # ================================================================
    #  JSON 导入/导出
    # ================================================================

    def export_to_json(self, filepath: str):
        """将整个数据库导出为 JSON 文件"""
        with self._session() as s:
            data = {
                "exported_at": _shared_now().isoformat(),
                "funds": [self._fund_to_dict(f) for f in db.get_all_funds(s)],
            }
            # 为了简洁，暂不导出完整 NAV，需要时单独调用
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, cls=_JSONEncoder)

    def import_from_json(self, filepath: str):
        """从 JSON 文件导入基金基础数据"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        with self._session() as s:
            for fund_data in data.get("funds", []):
                code = fund_data.pop("code", None)
                if code:
                    fund_data.pop("id", None)
                    fund_data.pop("created_at", None)
                    fund_data.pop("last_updated", None)
                    db.upsert_fund(s, code, **fund_data)

    # ================================================================
    #  内部辅助方法
    # ================================================================

    def _fund_to_dict(self, fund) -> Dict:
        return {
            "id": fund.id,
            "code": fund.code,
            "name": fund.name,
            "fund_type": fund.fund_type,
            "inception_date": fund.inception_date.isoformat()
            if fund.inception_date else None,
            "fund_size": fund.fund_size,
            "manager_name": fund.manager_name,
            "manager_tenure_days": fund.manager_tenure_days,
            "manager_return_pct": fund.manager_return_pct,
            "is_holding": fund.is_holding,
            "is_watching": fund.is_watching,
            "pending_amount": fund.pending_amount or 0.0,
            "watch_reason": fund.watch_reason,
            "data_freshness": fund.data_freshness,
            "last_updated": fund.last_updated.isoformat()
            if fund.last_updated else None,
        }

    def _snapshot_summary(self, snap) -> Dict:
        return {
            "id": snap.id,
            "analysis_date": snap.analysis_date.isoformat(),
            "portfolio_total_value": snap.portfolio_total_value,
        }

    def _build_analysis_dict(self, snap) -> Dict:
        """从 snapshot ORM 对象构建完整分析字典"""
        return {
            "id": snap.id,
            "analysis_date": snap.analysis_date.isoformat(),
            "data_completeness": snap.data_completeness,
            "market_summary": snap.market_summary,
            "portfolio_total_value": snap.portfolio_total_value,
            "portfolio_total_cost": snap.portfolio_total_cost,
            "cash_ratio_pct": snap.cash_ratio_pct,
            "scores": [{
                "fund_code": fs.fund.code if fs.fund else None,
                "fund_name": fs.fund.name if fs.fund else None,
                "data_completeness": fs.data_completeness,
                "composite_score": fs.composite_score,
                "score_level": fs.score_level,
                "macro_score": fs.macro_score,
                "macro_basis": fs.macro_basis,
                "meso_score": fs.meso_score,
                "meso_basis": fs.meso_basis,
                "micro_score": fs.micro_score,
                "micro_basis": fs.micro_basis,
                "macro_detail": fs.macro_detail,
                "meso_detail": fs.meso_detail,
                "micro_detail": fs.micro_detail,
                "recommendation": fs.recommendation,
                "current_position_pct": fs.current_position_pct,
                "target_position_pct": fs.target_position_pct,
                "dca_amount": fs.dca_amount,
                "dca_frequency": fs.dca_frequency,
                "stop_profit_pct": fs.stop_profit_pct,
                "stop_loss_pct": fs.stop_loss_pct,
                "action_logic": fs.action_logic,
                "key_metrics": fs.key_metrics,
            } for fs in snap.scores],
            "recommendations": [{
                "fund_code": r.fund_code,
                "fund_name": r.fund_name,
                "rec_type": r.rec_type,
                "rec_logic": r.rec_logic,
                "target_return_pct": r.target_return_pct,
                "stop_loss_pct": r.stop_loss_pct,
                "pearson_r": r.pearson_r,
                "hold_period_days": r.hold_period_days,
                "complementarity": r.complementarity,
                "alternative_plan": r.alternative_plan,
                "expected_annual_return": r.expected_annual_return,
                "is_added_to_watchlist": r.is_added_to_watchlist,
            } for r in snap.recommendations],
            "stress_tests": [{
                "scenario_id": st.scenario_id,
                "scenario_desc": st.scenario_desc,
                "estimated_drawdown_pct": st.estimated_drawdown_pct,
                "portfolio_drawdown_pct": st.portfolio_drawdown_pct,
                "impact_amount": st.impact_amount,
            } for st in snap.stress_tests],
            "correlations": [{
                "pearson_r": c.pearson_r,
                "is_warning": c.is_warning,
            } for c in snap.correlations],
            "sector_concentrations": [{
                "sector_name": sc.sector_name,
                "total_weight_pct": sc.total_weight_pct,
                "is_warning": sc.is_warning,
            } for sc in snap.sector_concentrations],
        }
