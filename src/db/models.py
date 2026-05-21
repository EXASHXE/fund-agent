from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean, Text,
    ForeignKey, UniqueConstraint, JSON, create_engine
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Fund(Base):
    """基金基础信息 — 缓存自 AKShare 或用户输入"""
    __tablename__ = "fund"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False, comment="基金代码")
    name = Column(String(100), comment="基金名称")
    fund_type = Column(String(50), comment="QDII/Hybrid/Stock/ETF/Index 等")
    inception_date = Column(Date, comment="成立日期")
    fund_size = Column(Float, comment="基金规模(亿)")
    manager_name = Column(String(50), comment="基金经理")
    manager_tenure_days = Column(Integer, comment="经理任职天数")
    manager_return_pct = Column(Float, comment="经理任职回报(%)")
    is_holding = Column(Boolean, default=False, comment="是否持有")
    is_watching = Column(Boolean, default=False, comment="是否关注(推荐)清单")
    pending_amount = Column(Float, default=0.0, comment="待确认金额(元)")
    watch_reason = Column(String(500), comment="关注/推荐原因")
    data_freshness = Column(String(4), default="D", comment="数据新鲜度 A/B/C/D")
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    # 反向引用
    holdings = relationship("FundHolding", back_populates="fund", cascade="all, delete-orphan")
    dca = relationship("FundDCA", back_populates="fund", uselist=False, cascade="all, delete-orphan")
    nav_records = relationship("FundNAV", back_populates="fund", cascade="all, delete-orphan")
    performances = relationship("FundPerformance", back_populates="fund", cascade="all, delete-orphan")
    top_holdings = relationship("FundTopHolding", back_populates="fund", cascade="all, delete-orphan")
    sectors = relationship("FundSector", back_populates="fund", cascade="all, delete-orphan")
    holders = relationship("FundHolder", back_populates="fund", cascade="all, delete-orphan")
    scores = relationship("FundScore", back_populates="fund", cascade="all, delete-orphan")


class FundHolding(Base):
    """用户持仓买入记录"""
    __tablename__ = "fund_holding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    buy_date = Column(Date, nullable=False, comment="买入日期")
    amount = Column(Float, nullable=False, comment="买入金额(¥)")
    nav = Column(Float, comment="买入时净值")
    shares = Column(Float, comment="买入份额")
    after_1500 = Column(Boolean, default=False, comment="是否15:00后下单")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="holdings")


class FundDCA(Base):
    """定投策略配置"""
    __tablename__ = "fund_dca"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"),
                     unique=True, nullable=False)
    frequency = Column(String(20), comment="daily/weekly/biweekly/monthly")
    amount = Column(Float, comment="每次定投金额(¥)")
    next_date = Column(Date, comment="下次定投日期")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="dca")


class FundNAV(Base):
    """净值历史 — 日频"""
    __tablename__ = "fund_nav"
    __table_args__ = (UniqueConstraint("fund_id", "date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, comment="净值日期")
    nav = Column(Float, nullable=False, comment="单位净值")
    acc_nav = Column(Float, comment="累计净值")
    daily_return = Column(Float, comment="日收益率")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="nav_records")


class FundPerformance(Base):
    """绩效指标 — Layer 1 核心风险指标"""
    __tablename__ = "fund_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    calc_date = Column(Date, nullable=False, comment="计算日期")
    period = Column(String(10), comment="统计周期: 1y/3y/5y")
    annual_return = Column(Float, comment="年化收益率(%)")
    annual_volatility = Column(Float, comment="年化波动率(%)")
    max_drawdown = Column(Float, comment="最大回撤(%)")
    sharpe_ratio = Column(Float, comment="夏普比率")
    alpha = Column(Float, comment="Alpha")
    beta = Column(Float, comment="Beta")
    information_ratio = Column(Float, comment="信息比率")
    tracking_error = Column(Float, comment="跟踪误差(%)")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="performances")


class FundTopHolding(Base):
    """前十大重仓股 — Layer 1 增强数据"""
    __tablename__ = "fund_top_holding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    report_date = Column(Date, nullable=False, comment="报告期")
    stock_code = Column(String(10), comment="股票代码")
    stock_name = Column(String(50), comment="股票名称")
    weight_pct = Column(Float, comment="占净值比例(%)")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="top_holdings")


class FundSector(Base):
    """行业配置 — Layer 1 增强数据"""
    __tablename__ = "fund_sector"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    report_date = Column(Date, nullable=False, comment="报告期")
    sector_name = Column(String(50), comment="行业名称")
    weight_pct = Column(Float, comment="占净值比例(%)")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="sectors")


class FundHolder(Base):
    """持有人结构 — Layer 1 增强数据"""
    __tablename__ = "fund_holder"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    report_date = Column(Date, nullable=False, comment="报告期")
    institution_pct = Column(Float, comment="机构持有比例(%)")
    retail_pct = Column(Float, comment="个人持有比例(%)")
    internal_pct = Column(Float, comment="内部持有比例(%)")
    total_shares = Column(Float, comment="总份额(亿)")
    created_at = Column(DateTime, server_default=func.now())

    fund = relationship("Fund", back_populates="holders")


class AnalysisSnapshot(Base):
    """一次完整的分析快照 — Layer 3 输出容器"""
    __tablename__ = "analysis_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(DateTime, nullable=False, default=func.now(), comment="分析时间")
    data_completeness = Column(String(4), comment="整体数据完整度")
    market_summary = Column(Text, comment="市场概况摘要")
    portfolio_total_value = Column(Float, comment="组合总价值(¥)")
    portfolio_total_cost = Column(Float, comment="总成本(¥)")
    cash_ratio_pct = Column(Float, comment="现金比例(%)")
    created_at = Column(DateTime, server_default=func.now())

    scores = relationship("FundScore", back_populates="snapshot", cascade="all, delete-orphan")
    recommendations = relationship("FundRecommendation", back_populates="snapshot",
                                   cascade="all, delete-orphan")
    stress_tests = relationship("StressTest", back_populates="snapshot",
                                cascade="all, delete-orphan")
    correlations = relationship("Correlation", back_populates="snapshot",
                                cascade="all, delete-orphan")
    sector_concentrations = relationship("SectorConcentration", back_populates="snapshot",
                                         cascade="all, delete-orphan")


class FundScore(Base):
    """单基金评分 — Layer 2 打分结果"""
    __tablename__ = "fund_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("analysis_snapshot.id", ondelete="CASCADE"),
                         nullable=False)
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="CASCADE"), nullable=False)
    data_completeness = Column(String(1), comment="数据完整度 A/B/C/D")
    composite_score = Column(Integer, comment="综合评分 0-100")
    score_level = Column(String(10), comment="等级: green/yellow/orange/red")
    score_confidence = Column(Float, comment="评分置信度 0-1")
    # 三大维度得分
    macro_score = Column(Integer, comment="宏观得分")
    macro_basis = Column(Text, comment="宏观依据摘要")
    meso_score = Column(Integer, comment="中观得分（可能为 NULL='未评分'）")
    meso_basis = Column(Text, comment="中观依据摘要")
    micro_score = Column(Integer, comment="微观得分")
    micro_basis = Column(Text, comment="微观依据摘要")
    # 详细评分
    macro_detail = Column(JSON, comment="宏观详细: {market_cycle, liquidity, valuation}")
    meso_detail = Column(JSON, comment="中观详细: {sector_prosperity, sector_pe, policy, rotation}")
    micro_detail = Column(JSON, comment="微观详细: {manager, alpha, drawdown, sharpe, institution}")
    feature_matrix = Column(JSON, comment="量化特征矩阵")
    factor_matrix = Column(JSON, comment="评分因子拆解矩阵")
    trend_matrix = Column(JSON, comment="趋势预测矩阵")
    operation_advice = Column(JSON, comment="操作建议矩阵")
    # 操作建议
    recommendation = Column(String(20), comment="买入/持有/减仓/止盈/止损/暂停定投/恢复定投/逢低加仓")
    current_position_pct = Column(Float, comment="当前仓位%")
    target_position_pct = Column(Float, comment="目标仓位%")
    dca_amount = Column(Float, comment="建议定投金额(¥)")
    dca_frequency = Column(String(20), comment="建议定投频率")
    stop_profit_pct = Column(Float, comment="止盈线(%)")
    stop_loss_pct = Column(Float, comment="止损线(%)")
    action_logic = Column(Text, comment="行动逻辑（≤3 句）")
    key_metrics = Column(Text, comment="关键监控指标（换行分隔）")
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("AnalysisSnapshot", back_populates="scores")
    fund = relationship("Fund", back_populates="scores")


class FundRecommendation(Base):
    """基金推荐 — Layer 3 推荐模块输出"""
    __tablename__ = "fund_recommendation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("analysis_snapshot.id", ondelete="CASCADE"),
                         nullable=False)
    fund_code = Column(String(10), nullable=False, comment="推荐基金代码")
    fund_name = Column(String(100), comment="推荐基金名称")
    rec_type = Column(String(10), comment="short(短期博弈) / long(长期稳健)")
    rec_logic = Column(Text, comment="推荐逻辑")
    target_return_pct = Column(Float, comment="目标收益(%)")
    stop_loss_pct = Column(Float, comment="止损线(%)")
    pearson_r = Column(Float, comment="与现有持仓 Pearson r")
    hold_period_days = Column(Integer, comment="建议持有天数（短期）")
    complementarity = Column(Text, comment="与组合互补性（长期）")
    alternative_plan = Column(Text, comment="替代预案（长期）")
    expected_annual_return = Column(String(50), comment="长期年化预期")
    is_added_to_watchlist = Column(Boolean, default=False, comment="是否已加入关注清单")
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("AnalysisSnapshot", back_populates="recommendations")


class StressTest(Base):
    """情景压力测试 — Layer 2.3 结果"""
    __tablename__ = "stress_test"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("analysis_snapshot.id", ondelete="CASCADE"),
                         nullable=False)
    scenario_id = Column(String(10), comment="S1/S2/S3/S4")
    scenario_desc = Column(String(200), comment="情景描述")
    fund_id = Column(Integer, ForeignKey("fund.id", ondelete="SET NULL"),
                     comment="受影响基金")
    estimated_drawdown_pct = Column(Float, comment="预估单基金回撤(%)")
    portfolio_drawdown_pct = Column(Float, comment="预估组合回撤(%)")
    impact_amount = Column(Float, comment="影响金额(¥)")
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("AnalysisSnapshot", back_populates="stress_tests")


class Correlation(Base):
    """基金相关性矩阵 — Layer 2.2 结果"""
    __tablename__ = "correlation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("analysis_snapshot.id", ondelete="CASCADE"),
                         nullable=False)
    fund_id_1 = Column(Integer, ForeignKey("fund.id", ondelete="SET NULL"),
                       comment="基金1")
    fund_id_2 = Column(Integer, ForeignKey("fund.id", ondelete="SET NULL"),
                       comment="基金2")
    pearson_r = Column(Float, comment="Pearson 相关系数")
    is_warning = Column(Boolean, default=False, comment=">0.85 警告")
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("AnalysisSnapshot", back_populates="correlations")


class SectorConcentration(Base):
    """行业集中度分析 — Layer 2.2 结果"""
    __tablename__ = "sector_concentration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("analysis_snapshot.id", ondelete="CASCADE"),
                         nullable=False)
    sector_name = Column(String(50), comment="行业名称")
    total_weight_pct = Column(Float, comment="合计权重(%)")
    is_warning = Column(Boolean, default=False, comment=">50% 黄色 / >70% 红色")
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("AnalysisSnapshot", back_populates="sector_concentrations")
