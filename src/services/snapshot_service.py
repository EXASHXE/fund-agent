"""Snapshot persistence and portfolio YAML roll-forward service."""

from __future__ import annotations

from src.config.shared import dca_effective_date, now as shared_now


def save_snapshot(store, scores, stress_tests, correlations, holdings_data=None):
    """Persist one analysis snapshot to storage."""
    try:
        score_data = [score_snapshot_payload(score) for score in scores]

        corr_data = []
        if not correlations.empty:
            codes_list = list(correlations.columns)
            for i, code_a in enumerate(codes_list):
                for code_b in codes_list[i + 1:]:
                    corr = correlations.loc[code_a, code_b]
                    corr_data.append({
                        "fund_code_1": code_a,
                        "fund_code_2": code_b,
                        "pearson_r": round(float(corr), 4),
                        "is_warning": abs(corr) > 0.85,
                    })

        snapshot_id = store.save_analysis({
            "analysis_date": shared_now(),
            "market_summary": "请参考 report.md",
            "portfolio_total_value": (holdings_data or {}).get("total_value"),
            "portfolio_total_cost": (holdings_data or {}).get("total_cost"),
            "scores": score_data,
            "stress_tests": sanitize_stress_tests_for_snapshot(stress_tests),
            "correlations": corr_data,
        })
        print(f"快照已保存: ID={snapshot_id}")
    except Exception as exc:
        print(f"[WARN] 快照保存失败: {exc}")


def score_snapshot_payload(score):
    """Build the database-safe score payload used by analysis snapshots."""
    return {
        "fund_code": score["fund_code"],
        "data_completeness": score["data_completeness"],
        "composite_score": score["composite_score"],
        "score_level": score["score_level"],
        "score_confidence": score.get("score_confidence"),
        "macro_score": score["macro_score"],
        "macro_basis": score.get("macro_basis", ""),
        "macro_detail": score.get("macro_detail", {}),
        "meso_score": score.get("meso_score"),
        "meso_basis": score.get("meso_basis", ""),
        "meso_detail": score.get("meso_detail", {}),
        "micro_score": score["micro_score"],
        "micro_basis": score.get("micro_basis", ""),
        "micro_detail": score.get("micro_detail", {}),
        "feature_matrix": score.get("feature_matrix"),
        "factor_matrix": score.get("factor_matrix"),
        "trend_matrix": score.get("trend_evidence") or score.get("trend_matrix"),
        "operation_advice": score.get("operation_advice"),
        "recommendation": score["recommendation"],
        "stop_profit_pct": score["stop_profit_pct"],
        "stop_loss_pct": score["stop_loss_pct"],
        "action_logic": score["action_logic"],
        "key_metrics": (
            f"波动率:{score.get('annual_volatility','N/A')}; "
            f"夏普:{score.get('sharpe_1y','N/A')}"
        ),
    }


def sanitize_stress_tests_for_snapshot(stress_tests):
    allowed = {
        "scenario_id",
        "scenario_desc",
        "fund_code",
        "estimated_drawdown_pct",
        "portfolio_drawdown_pct",
        "impact_amount",
    }
    return [
        {key: value for key, value in (item or {}).items() if key in allowed}
        for item in (stress_tests or [])
    ]


def should_snapshot_after_analyze(args) -> bool:
    return getattr(args, "snapshot_after", True)


def perform_snapshot(config_path):
    """Roll executed DCA purchases into the portfolio YAML."""
    import yaml

    from src.analysis.holdings import _is_business_day, _next_dca_date
    from src.config.loader import load_portfolio_config
    from src.config.schema import Purchase

    config = load_portfolio_config(config_path)
    today = dca_effective_date()

    for holding in config.holdings:
        if holding.dca and holding.dca.enabled:
            dca = holding.dca
            start = dca.start_date or today

            current = start
            while current <= today:
                if _is_business_day(current):
                    already_exists = any(
                        purchase.date == current and purchase.amount == dca.amount
                        for purchase in holding.purchases
                    )
                    if not already_exists:
                        holding.purchases.append(Purchase(date=current, amount=dca.amount))
                current = _next_dca_date(current, dca.frequency.value, dca.day_of_week)

            dca.start_date = current

    raw = config.model_dump(mode="json")

    def fmt_date(value):
        if isinstance(value, str):
            return value
        return value.isoformat()

    for holding in raw.get("holdings", []):
        for purchase in holding.get("purchases", []):
            if purchase.get("date"):
                purchase["date"] = fmt_date(purchase["date"])
        dca = holding.get("dca")
        if dca and dca.get("start_date"):
            dca["start_date"] = fmt_date(dca["start_date"])

    with open(config_path, "w", encoding="utf-8") as handle:
        yaml.dump(raw, handle, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"持仓已更新: {config_path}")
