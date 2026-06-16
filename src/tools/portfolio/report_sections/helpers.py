"""Helper functions for report section building — formatting, coercion, and utilities."""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _unique_strings(values: list[Any]) -> list[str]:
    from src.skills_runtime.common.strings import unique_strings

    return unique_strings(values, skip_empty=True)


def _money(value: Any) -> str:
    try:
        amount = float(value or 0.0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.2f}"


def _money_or_missing(value: Any, *, likely_missing: bool = False, lang: str = "zh") -> str:
    """Format money value, returning N/A when value is None or likely missing.

    Args:
        value: The monetary value to format.
        likely_missing: If True, treat the value as likely missing (e.g. current_value=0
            when 80%+ holdings have zero). Returns N/A instead of "0.00".
        lang: Language for the missing indicator — "zh" returns "无法计算", "en" returns "N/A".

    Returns:
        Formatted money string, or missing indicator when value is absent/likely missing.
    """
    missing_text = "N/A" if lang == "en" else "无法计算"
    if value is None:
        return missing_text
    if likely_missing:
        return missing_text
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return missing_text
    return f"{amount:,.2f}"


def _pct(value: Any) -> str:
    try:
        pct = float(value or 0.0) * 100
    except (TypeError, ValueError):
        pct = 0.0
    return f"{pct:.2f}%"


def _fixed(value: Any, digits: int) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.{digits}f}"


def _largest_weight(values: dict[str, Any]) -> tuple[str, Any]:
    sortable: list[tuple[str, float]] = []
    for key, value in values.items():
        try:
            sortable.append((str(key), float(value)))
        except (TypeError, ValueError):
            continue
    if not sortable:
        return ("unknown", 0.0)
    sortable.sort(key=lambda item: (-item[1], item[0]))
    return sortable[0]


def _risk_counts_by_severity(risk_flags: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for flag in risk_flags:
        if not isinstance(flag, dict):
            continue
        severity = str(flag.get("severity") or "unspecified")
        counts[severity] = counts.get(severity, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _best_total_return(fund_metrics: dict[str, Any]) -> tuple[str, float] | None:
    candidates: list[tuple[str, float]] = []
    for fund_code, metrics in fund_metrics.items():
        if not isinstance(metrics, dict):
            continue
        try:
            candidates.append((str(fund_code), float(metrics.get("total_return"))))
        except (TypeError, ValueError):
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates[0]


def _artifact(context: dict[str, Any], key: str) -> dict[str, Any]:
    artifacts = context["artifacts"]
    report = context["report"]
    return _as_dict(artifacts.get(key) or report.get(key))


def _missing_gap_codes(gap: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key in sorted(gap):
        if key == "details":
            continue
        if key.startswith("missing_") and gap.get(key) is True:
            result.append(key)
    return result


def _portfolio_summary(context: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(context["artifacts"].get("portfolio_summary") or context["report"].get("portfolio_metrics"))


def _current_value_likely_missing(context: dict[str, Any]) -> bool:
    """Check if current_value is likely missing from the portfolio data."""
    ps = _portfolio_summary(context)
    if ps.get("current_value_likely_missing"):
        return True
    # Also check factor_snapshot data_quality if available
    fs = _as_dict(context["artifacts"].get("factor_snapshot"))
    return bool(fs.get("data_quality", {}).get("current_value_likely_missing"))
