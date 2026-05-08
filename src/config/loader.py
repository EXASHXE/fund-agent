"""YAML 配置文件加载、校验、默认值填充"""
import os
import yaml
from typing import Optional
from pydantic import ValidationError
from src.config.schema import PortfolioConfig


def load_portfolio_config(config_path: str) -> PortfolioConfig:
    """加载并校验 YAML 配置文件。"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError("配置文件为空")

    if "profile" not in raw:
        raw["profile"] = {}
    if "strategy" not in raw:
        raw["strategy"] = {}
    if "holdings" not in raw:
        raw["holdings"] = []
    if "watchlist" not in raw:
        raw["watchlist"] = []

    try:
        config = PortfolioConfig.model_validate(raw)
    except ValidationError as e:
        raise ValidationError.from_exception_data(
            title="配置校验失败",
            line_errors=e.errors(),
        )

    return config


def import_to_database(config: PortfolioConfig, db_path: Optional[str] = None):
    """将配置文件中的持仓数据导入数据库。"""
    from src.db.storage import FundStorage

    store = FundStorage(db_path)

    for holding in config.holdings:
        code = holding.code
        name = holding.name

        if not name:
            try:
                import akshare as ak
                df = ak.fund_individual_basic_info_xq(symbol=code)
                info = dict(zip(df["item"], df["value"]))
                name = info.get("基金名称", code)
            except Exception:
                name = code

        store.save_fund(
            code=code,
            name=name,
            fund_type=holding.type.value,
            is_holding=True,
        )

        for purchase in holding.purchases:
            store.save_holding(
                fund_code=code,
                buy_date=purchase.date,
                amount=purchase.amount,
                nav=purchase.nav,
                after_1500=purchase.after_1500 if hasattr(purchase, 'after_1500') else False,
            )

        if holding.dca and holding.dca.enabled:
            dca = holding.dca
            store.save_dca(
                fund_code=code,
                frequency=dca.frequency.value,
                amount=dca.amount,
                is_active=True,
            )

    for watch_code in config.watchlist:
        store.save_fund(code=watch_code, is_watching=True)

    print(f"导入完成: {len(config.holdings)} 只基金, {len(config.watchlist)} 只自选")


def generate_sample_yaml(output_path: str):
    """生成示例配置文件"""
    sample = """# fund-portfolio.yaml — 基金持仓与策略配置

# === 用户画像 ===
profile:
  risk_tolerance: moderate       # conservative | moderate | aggressive
  investment_horizon: 3-5年
  target_return: 0.10
  max_drawdown_tolerance: 0.20

# === 持仓基金 ===
holdings:
  - code: "008253"
    name: 华宝致远混合(QDII)A
    type: qdii
    currency: CNY
    purchases:
      - date: 2025-12-08
        amount: 2500
    dca:
      enabled: true
      frequency: weekly
      amount: 100
      day_of_week: wed
      start_date: 2025-12-08

# === 策略参数覆写 (可选，不填用默认值) ===
strategy:
  scoring:
    macro_weight: 0.20
    meso_weight: 0.30
    micro_weight: 0.50
  stop_profit_loss:
    profit_multiplier: 2.0
    loss_multiplier: 1.5
  rebalance:
    max_single_position: 0.30
    correlation_alert: 0.75

# === 自选池 ===
watchlist: []
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sample)
    print(f"示例配置已生成: {output_path}")
