"""
数据库连接管理与基础 CRUD 操作。
默认使用 SQLite，数据库文件存储在项目根目录的 data/ 下。
"""
import os
from datetime import date, datetime
from src.config.shared import now as _shared_now
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, func, and_, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Fund, FundHolding, FundDCA, FundNAV, FundPerformance
from .models import FundTopHolding, FundSector, FundHolder
from .models import AnalysisSnapshot, FundScore, FundRecommendation
from .models import StressTest, Correlation, SectorConcentration

# 数据库文件位置
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "fund_agent.db")


def get_engine(db_path: str = None):
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def init_db(db_path: str = None):
    """初始化数据库，创建所有表"""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    _ensure_fund_score_columns(engine)
    return engine


def _ensure_fund_score_columns(engine):
    """Lightweight SQLite migration for newly added score JSON columns."""
    inspector = inspect(engine)
    if "fund_score" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("fund_score")}
    additions = {
        "score_confidence": "FLOAT",
        "feature_matrix": "JSON",
        "factor_matrix": "JSON",
        "trend_matrix": "JSON",
        "operation_advice": "JSON",
    }
    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE fund_score ADD COLUMN {name} {sql_type}"))


def get_session(db_path: str = None) -> Session:
    """获取数据库会话"""
    engine = get_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ============================
# Fund CRUD
# ============================

def upsert_fund(session: Session, code: str, **kwargs) -> Fund:
    """插入或更新基金基本信息"""
    fund = session.query(Fund).filter(Fund.code == code).first()
    if fund:
        for k, v in kwargs.items():
            if hasattr(fund, k):
                setattr(fund, k, v)
        fund.last_updated = _shared_now()
    else:
        fund = Fund(code=code, **kwargs)
        session.add(fund)
    session.commit()
    return fund


def get_fund(session: Session, code: str) -> Optional[Fund]:
    return session.query(Fund).filter(Fund.code == code).first()


def get_holding_funds(session: Session) -> List[Fund]:
    return session.query(Fund).filter(Fund.is_holding == True).all()


def get_watching_funds(session: Session) -> List[Fund]:
    return session.query(Fund).filter(Fund.is_watching == True).all()


def get_all_funds(session: Session) -> List[Fund]:
    return session.query(Fund).all()


# ============================
# FundHolding CRUD
# ============================

def holding_exists(session: Session, fund_id: int, buy_date: date, amount: float) -> bool:
    """检查相同持仓记录是否已存在"""
    return session.query(FundHolding).filter(
        FundHolding.fund_id == fund_id,
        FundHolding.buy_date == buy_date,
        FundHolding.amount == amount,
    ).first() is not None


def add_holding(session: Session, fund_id: int, buy_date: date, amount: float,
                nav: float = None, shares: float = None,
                after_1500: bool = False) -> FundHolding:
    holding = FundHolding(fund_id=fund_id, buy_date=buy_date,
                          amount=amount, nav=nav, shares=shares,
                          after_1500=after_1500)
    session.add(holding)
    session.commit()
    return holding


def get_holdings(session: Session, fund_id: int = None) -> List[FundHolding]:
    q = session.query(FundHolding)
    if fund_id:
        q = q.filter(FundHolding.fund_id == fund_id)
    return q.order_by(FundHolding.buy_date).all()


# ============================
# FundDCA CRUD
# ============================

def upsert_dca(session: Session, fund_id: int, **kwargs) -> FundDCA:
    dca = session.query(FundDCA).filter(FundDCA.fund_id == fund_id).first()
    if dca:
        for k, v in kwargs.items():
            if hasattr(dca, k):
                setattr(dca, k, v)
    else:
        dca = FundDCA(fund_id=fund_id, **kwargs)
        session.add(dca)
    session.commit()
    return dca


# ============================
# FundNAV CRUD
# ============================

def upsert_nav(session: Session, fund_id: int, date_val: date, nav: float,
               **kwargs) -> FundNAV:
    """插入或更新净值记录"""
    record = session.query(FundNAV).filter(
        and_(FundNAV.fund_id == fund_id, FundNAV.date == date_val)
    ).first()
    if record:
        record.nav = nav
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
    else:
        record = FundNAV(fund_id=fund_id, date=date_val, nav=nav, **kwargs)
        session.add(record)
    session.commit()
    return record


def bulk_insert_nav(session: Session, fund_id: int,
                    records: List[Dict[str, Any]]) -> int:
    """批量插入净值记录，records = [{"date": ..., "nav": ..., ...}, ...]"""
    count = 0
    for r in records:
        existing = session.query(FundNAV).filter(
            and_(FundNAV.fund_id == fund_id, FundNAV.date == r["date"])
        ).first()
        if not existing:
            session.add(FundNAV(fund_id=fund_id, **r))
            count += 1
    session.commit()
    return count


def get_nav_history(session: Session, fund_id: int,
                    start_date: date = None, end_date: date = None) -> List[FundNAV]:
    q = session.query(FundNAV).filter(FundNAV.fund_id == fund_id)
    if start_date:
        q = q.filter(FundNAV.date >= start_date)
    if end_date:
        q = q.filter(FundNAV.date <= end_date)
    return q.order_by(FundNAV.date).all()


# ============================
# FundPerformance CRUD
# ============================

def upsert_performance(session: Session, fund_id: int, calc_date: date,
                       period: str, **kwargs) -> FundPerformance:
    record = session.query(FundPerformance).filter(
        and_(FundPerformance.fund_id == fund_id,
             FundPerformance.calc_date == calc_date,
             FundPerformance.period == period)
    ).first()
    if record:
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
    else:
        record = FundPerformance(fund_id=fund_id, calc_date=calc_date,
                                 period=period, **kwargs)
        session.add(record)
    session.commit()
    return record


# ============================
# FundTopHolding / FundSector / FundHolder CRUD
# ============================

def replace_top_holdings(session: Session, fund_id: int, report_date: date,
                         holdings: List[Dict[str, Any]]):
    """替换某报告期的前十大持仓"""
    session.query(FundTopHolding).filter(
        and_(FundTopHolding.fund_id == fund_id,
             FundTopHolding.report_date == report_date)
    ).delete()
    for h in holdings:
        session.add(FundTopHolding(fund_id=fund_id, report_date=report_date, **h))
    session.commit()


def replace_sectors(session: Session, fund_id: int, report_date: date,
                    sectors: List[Dict[str, Any]]):
    """替换行业配置"""
    session.query(FundSector).filter(
        and_(FundSector.fund_id == fund_id,
             FundSector.report_date == report_date)
    ).delete()
    for s in sectors:
        session.add(FundSector(fund_id=fund_id, report_date=report_date, **s))
    session.commit()


def replace_holders(session: Session, fund_id: int, report_date: date,
                    holder_data: Dict[str, Any]):
    """替换持有人结构（每期只有一条记录）"""
    session.query(FundHolder).filter(
        and_(FundHolder.fund_id == fund_id,
             FundHolder.report_date == report_date)
    ).delete()
    session.add(FundHolder(fund_id=fund_id, report_date=report_date, **holder_data))
    session.commit()


# ============================
# AnalysisSnapshot CRUD
# ============================

def create_snapshot(session: Session, **kwargs) -> AnalysisSnapshot:
    snapshot = AnalysisSnapshot(**kwargs)
    session.add(snapshot)
    session.commit()
    return snapshot


def get_latest_snapshot(session: Session) -> Optional[AnalysisSnapshot]:
    return session.query(AnalysisSnapshot).order_by(
        AnalysisSnapshot.analysis_date.desc()
    ).first()


def get_snapshots(session: Session, limit: int = 20) -> List[AnalysisSnapshot]:
    return session.query(AnalysisSnapshot).order_by(
        AnalysisSnapshot.analysis_date.desc()
    ).limit(limit).all()


# ============================
# FundScore CRUD
# ============================

def add_score(session: Session, snapshot_id: int, fund_id: int, **kwargs) -> FundScore:
    score = FundScore(snapshot_id=snapshot_id, fund_id=fund_id, **kwargs)
    session.add(score)
    session.commit()
    return score


def get_scores(session: Session, snapshot_id: int) -> List[FundScore]:
    return session.query(FundScore).filter(
        FundScore.snapshot_id == snapshot_id
    ).all()


def get_fund_score_history(session: Session, fund_id: int,
                           limit: int = 10) -> List[FundScore]:
    """获取某基金的历史评分记录"""
    return session.query(FundScore).filter(
        FundScore.fund_id == fund_id
    ).join(AnalysisSnapshot).order_by(
        AnalysisSnapshot.analysis_date.desc()
    ).limit(limit).all()


# ============================
# FundRecommendation CRUD
# ============================

def add_recommendation(session: Session, snapshot_id: int, **kwargs) -> FundRecommendation:
    rec = FundRecommendation(snapshot_id=snapshot_id, **kwargs)
    session.add(rec)
    session.commit()
    return rec


def get_recommendations(session: Session, snapshot_id: int = None,
                        rec_type: str = None) -> List[FundRecommendation]:
    q = session.query(FundRecommendation)
    if snapshot_id:
        q = q.filter(FundRecommendation.snapshot_id == snapshot_id)
    if rec_type:
        q = q.filter(FundRecommendation.rec_type == rec_type)
    return q.all()


# ============================
# StressTest / Correlation / SectorConcentration CRUD
# ============================

def add_stress_tests(session: Session, snapshot_id: int,
                     tests: List[Dict[str, Any]]):
    for t in tests:
        session.add(StressTest(snapshot_id=snapshot_id, **t))
    session.commit()


def add_correlations(session: Session, snapshot_id: int,
                     pairs: List[Dict[str, Any]]):
    for p in pairs:
        session.add(Correlation(snapshot_id=snapshot_id, **p))
    session.commit()


def add_sector_concentrations(session: Session, snapshot_id: int,
                              sectors: List[Dict[str, Any]]):
    for s in sectors:
        session.add(SectorConcentration(snapshot_id=snapshot_id, **s))
    session.commit()
