"""
基金持仓管理 UI — Streamlit 应用

启动: streamlit run src/ui/app.py
"""
import streamlit as st
import yaml
import sys
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from src.config.shared import today as _shared_today, now as _shared_now

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.schema import (
    PortfolioConfig, FundHolding, Purchase, DCAStrategy, Calibration,
    FundType, DCAFrequency, RiskTolerance,
)
from src.config.loader import load_portfolio_config

CONFIG_PATH = Path(os.environ.get("FUND_CONFIG", "fund-portfolio.yaml"))

FUND_TYPE_LABELS = {
    "domestic": "国内混合",
    "qdii": "QDII 海外",
    "etf": "ETF 联接",
    "index": "指数",
}

FREQ_LABELS = {
    "daily": "每日",
    "weekly": "每周",
    "biweekly": "每两周",
    "monthly": "每月",
}

RISK_LABELS = {
    "conservative": "保守",
    "moderate": "稳健",
    "aggressive": "进取",
}


def load_config() -> PortfolioConfig:
    if not CONFIG_PATH.exists():
        st.error(f"配置文件不存在: {CONFIG_PATH}")
        st.stop()
    return load_portfolio_config(str(CONFIG_PATH))


def save_config(config: PortfolioConfig):
    raw = config.model_dump(mode="json")

    def fmt_date(d):
        if isinstance(d, str):
            return d
        if isinstance(d, date):
            return d.isoformat()
        return d

    for h in raw.get("holdings", []):
        for p in h.get("purchases", []):
            if p.get("date"):
                p["date"] = fmt_date(p["date"])
        dca = h.get("dca")
        if dca and dca.get("start_date"):
            dca["start_date"] = fmt_date(dca["start_date"])
        for c in h.get("calibrations", []):
            if c.get("cal_date"):
                c["cal_date"] = fmt_date(c["cal_date"])

    config_path = str(CONFIG_PATH)
    backup_path = f"{config_path}.{_shared_now().strftime('%Y-%m-%d')}.bak"
    if os.path.exists(config_path):
        shutil.copy2(config_path, backup_path)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    _cleanup_bak_files(config_path)


def _cleanup_bak_files(config_path: str, keep: int = 1):
    import glob
    import re
    pattern = f"{config_path}.*.bak"
    files = glob.glob(pattern)
    files_with_date = []
    for f in files:
        m = re.search(r'(\d{4}-\d{2}-\d{2})\.bak$', f)
        if m:
            files_with_date.append((m.group(1), f))
    files_with_date.sort(key=lambda x: x[0], reverse=True)
    for _, old in files_with_date[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass


def find_holding(config: PortfolioConfig, code: str) -> tuple:
    for i, h in enumerate(config.holdings):
        if h.code == code:
            return i, h
    return -1, None


def main():
    st.set_page_config(page_title="基金持仓管理", page_icon="📊", layout="wide")
    st.title("基金持仓管理")

    if "config" not in st.session_state:
        st.session_state.config = load_config()

    config = st.session_state.config

    tabs = st.tabs(["持仓总览", "基金详情", "定投管理", "新增/删除"])

    with tabs[0]:
        render_overview(config)

    with tabs[1]:
        render_fund_detail(config)

    with tabs[2]:
        render_dca_management(config)

    with tabs[3]:
        render_add_delete(config)


def render_overview(config: PortfolioConfig):
    st.subheader("组合总览")

    cols = st.columns(4)
    total_cost = 0.0
    total_pending = 0.0

    for h in config.holdings:
        if h.shares and h.avg_cost:
            total_cost += h.shares * h.avg_cost
        total_pending += h.pending_amount

    cols[0].metric("基金数量", len(config.holdings))
    cols[1].metric("总投入成本", f"¥{total_cost:,.2f}")
    cols[2].metric("待确认金额", f"¥{total_pending:,.2f}")
    cols[3].metric("持仓份额(估算)", f"{sum(h.shares or 0 for h in config.holdings):,.0f}")

    st.subheader("资产分布")
    fund_names = []
    fund_costs = []
    for h in config.holdings:
        fund_names.append(f"{h.name} ({h.code})")
        if h.shares and h.avg_cost:
            fund_costs.append(round(h.shares * h.avg_cost, 2))
        else:
            fund_costs.append(0.01)

    df_pie = {"基金": fund_names, "投入成本": fund_costs}
    st.dataframe(df_pie, width='stretch', hide_index=True)

    st.subheader("基金详情表")
    rows = []
    for h in config.holdings:
        value = round(h.shares * h.avg_cost, 2) if (h.shares and h.avg_cost) else 0
        rows.append({
            "代码": h.code,
            "名称": h.name,
            "类型": FUND_TYPE_LABELS.get(h.type.value, h.type.value),
            "费率": f"{h.fee_rate:.2%}",
            "成本价": h.avg_cost if h.avg_cost else "-",
            "份额": f"{h.shares:,.2f}" if h.shares else "-",
            "投入成本": f"¥{value:,.2f}",
            "待确认": f"¥{h.pending_amount:,.0f}",
            "结算延迟": f"T+{h.settle_delay}",
            "定投": "启用" if (h.dca and h.dca.enabled) else "关闭",
        })
    st.dataframe(rows, width='stretch', hide_index=True)


def render_fund_detail(config: PortfolioConfig):
    codes = [h.code for h in config.holdings]
    if not codes:
        st.info("暂无持仓基金")
        return

    selected_code = st.selectbox("选择基金", codes,
                                  format_func=lambda c: f"{c} — {next(h.name for h in config.holdings if h.code == c)}")

    idx, holding = find_holding(config, selected_code)
    if idx < 0:
        return

    st.subheader(f"{holding.name}（{holding.code}）")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_fee = st.number_input("手续费率", value=float(holding.fee_rate),
                                   min_value=0.0, max_value=0.1, step=0.0001,
                                   format="%.4f", key=f"fee_{selected_code}")
        if new_fee is not None:
            holding.fee_rate = new_fee
    with col2:
        new_avg = st.number_input("成本价", value=float(holding.avg_cost or 0),
                                   min_value=0.0, step=0.0001, format="%.4f",
                                   key=f"avg_{selected_code}")
        if new_avg is not None and new_avg > 0:
            holding.avg_cost = new_avg
    with col3:
        new_shares = st.number_input("持有份额", value=float(holding.shares or 0),
                                      min_value=0.0, step=0.01, format="%.2f",
                                      key=f"shares_{selected_code}")
        if new_shares is not None and new_shares > 0:
            holding.shares = new_shares
    with col4:
        new_pending = st.number_input("待确认金额(元)", value=float(holding.pending_amount),
                                       min_value=0.0, step=1.0,
                                       key=f"pending_{selected_code}")
        if new_pending is not None:
            holding.pending_amount = new_pending

    st.caption(f"结算延迟: T+{holding.settle_delay} | 类型: {FUND_TYPE_LABELS.get(holding.type.value, holding.type.value)}")

    st.subheader("买入记录")
    purchase_data = []
    for i, p in enumerate(holding.purchases):
        purchase_data.append({
            "#": i + 1,
            "日期": p.date.isoformat() if isinstance(p.date, date) else str(p.date),
            "金额(元)": p.amount,
            "15:00后": "是" if p.after_1500 else "否",
            "净值": f"{p.nav:.4f}" if p.nav else "自动",
        })
    st.dataframe(purchase_data, width='stretch', hide_index=True)

    st.subheader("校准记录")
    cal_data = []
    for c in holding.calibrations:
        cal_data.append({
            "日期": c.cal_date.isoformat() if isinstance(c.cal_date, date) else str(c.cal_date),
            "真实份额": c.actual_shares,
        })
    if cal_data:
        st.dataframe(cal_data, width='stretch', hide_index=True)
    else:
        st.caption("暂无校准记录")

    if st.button("保存修改", key=f"save_{selected_code}"):
        save_config(config)
        st.session_state.config = load_config()
        st.success("已保存")
        st.rerun()


def render_dca_management(config: PortfolioConfig):
    st.subheader("定投策略管理")

    dca_funds = [h for h in config.holdings if h.dca and h.dca.enabled]
    no_dca = [h for h in config.holdings if not (h.dca and h.dca.enabled)]

    st.write(f"已启用定投: {len(dca_funds)} 只 | 未启用: {len(no_dca)} 只")

    for h in dca_funds:
        with st.expander(f"{h.name}（{h.code}）— {FREQ_LABELS.get(h.dca.frequency.value, h.dca.frequency.value)} ¥{h.dca.amount}"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                freq = st.selectbox("频率", list(FREQ_LABELS.keys()),
                                     format_func=lambda x: FREQ_LABELS[x],
                                     index=list(FREQ_LABELS.keys()).index(h.dca.frequency.value),
                                     key=f"dca_freq_{h.code}")
                h.dca.frequency = DCAFrequency(freq)
            with col2:
                h.dca.amount = st.number_input("每期金额(元)", value=float(h.dca.amount),
                                                min_value=1.0, step=50.0,
                                                key=f"dca_amt_{h.code}")
            with col3:
                dow_options = {"mon": "周一", "tue": "周二", "wed": "周三", "thu": "周四", "fri": "周五"}
                dow_keys = list(dow_options.keys())
                current_dow = h.dca.day_of_week or "mon"
                if current_dow not in dow_keys:
                    current_dow = "mon"
                dow_idx = dow_keys.index(current_dow)
                selected_dow = st.selectbox("定投日", dow_keys,
                                             format_func=lambda x: dow_options[x],
                                             index=dow_idx,
                                             key=f"dca_dow_{h.code}")
                h.dca.day_of_week = selected_dow
            with col4:
                start_str = h.dca.start_date.isoformat() if isinstance(h.dca.start_date, date) else str(h.dca.start_date) if h.dca.start_date else ""
                new_start = st.text_input("下次定投日期", value=start_str,
                                           key=f"dca_start_{h.code}")
                try:
                    from datetime import datetime
                    h.dca.start_date = datetime.strptime(new_start[:10], "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    pass

            if st.button("停用此定投", key=f"dca_disable_{h.code}"):
                h.dca.enabled = False
                save_config(config)
                st.session_state.config = load_config()
                st.success("已停用")
                st.rerun()

    for h in no_dca:
        with st.expander(f"{h.name}（{h.code}）— 未启用定投"):
            if st.button("启用手动定投", key=f"dca_enable_{h.code}"):
                h.dca = DCAStrategy(
                    enabled=True,
                    frequency=DCAFrequency.WEEKLY,
                    amount=100.0,
                    day_of_week="mon",
                    start_date=_shared_today(),
                )
                save_config(config)
                st.session_state.config = load_config()
                st.success("已启用")
                st.rerun()

    if st.button("保存所有定投修改", type="primary"):
        save_config(config)
        st.session_state.config = load_config()
        st.success("定投配置已保存")
        st.rerun()


def render_add_delete(config: PortfolioConfig):
    st.subheader("新增基金")

    col1, col2 = st.columns(2)
    with col1:
        new_code = st.text_input("基金代码(6位)", max_chars=6)
    with col2:
        new_type = st.selectbox("基金类型", list(FUND_TYPE_LABELS.keys()),
                                 format_func=lambda x: FUND_TYPE_LABELS[x])

    col3, col4 = st.columns(2)
    with col3:
        new_fee = st.number_input("费率", value=0.0015, min_value=0.0, max_value=0.1,
                                  step=0.0001, format="%.4f")
    with col4:
        new_settle = st.selectbox("结算延迟", [1, 2],
                                   format_func=lambda x: f"T+{x}",
                                   index=1 if new_type == "qdii" else 0)

    if st.button("添加基金", type="primary"):
        if not new_code or len(new_code) != 6:
            st.error("请输入6位基金代码")
        elif any(h.code == new_code for h in config.holdings):
            st.error("该基金已存在")
        else:
            try:
                import akshare as ak
                df = ak.fund_individual_basic_info_xq(symbol=new_code)
                info = dict(zip(df["item"], df["value"]))
                auto_name = info.get("基金名称", new_code)
            except Exception:
                auto_name = new_code

            config.holdings.append(FundHolding(
                code=new_code,
                name=auto_name,
                type=FundType(new_type),
                fee_rate=new_fee,
                settle_delay=new_settle,
            ))
            save_config(config)
            st.session_state.config = load_config()
            st.success(f"已添加: {new_code} {auto_name}")
            st.rerun()

    st.divider()
    st.subheader("删除基金")

    del_code = st.selectbox("选择要删除的基金",
                             [h.code for h in config.holdings],
                             format_func=lambda c: f"{c} — {next(h.name for h in config.holdings if h.code == c)}")

    if st.button("删除选中基金", type="secondary"):
        idx, holding = find_holding(config, del_code)
        if idx >= 0:
            st.warning(f"确认删除 {holding.name}（{holding.code}）？")
            if st.button("确认删除", type="primary", key="confirm_del"):
                del config.holdings[idx]
                save_config(config)
                st.session_state.config = load_config()
                st.success("已删除")
                st.rerun()


if __name__ == "__main__":
    main()
