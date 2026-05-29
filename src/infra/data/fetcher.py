"""AKShare data fetchers used by the scoring and holding pipeline."""
from datetime import datetime
from typing import Dict

import pandas as pd


def fetch_fund_basic(code: str) -> Dict:
    try:
        import akshare as ak

        df = ak.fund_individual_basic_info_xq(symbol=code)
        info = dict(zip(df["item"], df["value"]))
        return {
            "code": code,
            "name": info.get("基金名称") or info.get("基金简称") or code,
            "fund_type": info.get("基金类型", ""),
            "inception_date": info.get("成立日期"),
            "size": info.get("基金规模"),
            "manager": info.get("基金经理") or info.get("现任基金经理", ""),
        }
    except Exception as exc:
        return {"code": code, "name": code, "error": str(exc)}


def fetch_fund_nav(code: str) -> pd.DataFrame:
    try:
        import akshare as ak

        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return pd.DataFrame()

        date_col = "净值日期" if "净值日期" in df.columns else "日期"
        nav_col = "单位净值" if "单位净值" in df.columns else df.columns[1]
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "净值日期", nav_col: "单位净值"})
        if "日增长率" not in df.columns:
            df["日增长率"] = df["单位净值"].astype(float).pct_change() * 100
        df["单位净值"] = df["单位净值"].astype(float)
        df = df.set_index("净值日期").sort_index()
        return df
    except Exception:
        return pd.DataFrame()


def fetch_fund_performance(code: str) -> Dict:
    try:
        import akshare as ak

        df = ak.fund_individual_analysis_xq(symbol=code)
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            period = row.get("周期") or row.get("item") or row.get("指标")
            if not period:
                continue
            result[str(period)] = {
                "annual_return": _to_float(row.get("年化收益率")),
                "annual_volatility": _to_float(row.get("年化波动率")),
                "max_drawdown": abs(_to_float(row.get("最大回撤"))),
                "sharpe_ratio": _to_float(row.get("夏普比率")),
            }
        return result
    except Exception as exc:
        return {"error": str(exc)}


def fetch_fund_holdings(code: str) -> pd.DataFrame:
    try:
        import akshare as ak

        year = datetime.now().year
        return ak.fund_portfolio_hold_em(symbol=code, date=str(year))
    except Exception:
        return pd.DataFrame()


def fetch_fund_sectors(code: str) -> pd.DataFrame:
    try:
        import akshare as ak

        return ak.fund_portfolio_industry_allocation_em(symbol=code, date=str(datetime.now().year))
    except Exception:
        return pd.DataFrame()


def fetch_holder_structure(code: str) -> pd.DataFrame:
    try:
        import akshare as ak

        df = ak.fund_hold_structure_em()
        if df is not None and not df.empty and "基金代码" in df.columns:
            return df[df["基金代码"].astype(str).str.zfill(6) == str(code).zfill(6)]
        return df
    except Exception:
        return pd.DataFrame()


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except ValueError:
        return 0.0
