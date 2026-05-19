"""Agent-generated news keyword cache and request builder."""
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


CACHE_VERSION = "news_keyword_profiles.v1"
REQUEST_VERSION = "news_keyword_request.v1"
MAX_CACHE_AGE_DAYS = 90


def default_keyword_cache_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "data" / "cache" / "news_keyword_profiles.json")


def load_valid_keyword_cache(
    path: str,
    holding_codes: List[str],
    today: date,
    max_age_days: int = MAX_CACHE_AGE_DAYS,
) -> Optional[Dict[str, Any]]:
    payload = _read_json(path)
    if not payload:
        return None
    if payload.get("cache_version") != CACHE_VERSION:
        return None

    expected_codes = sorted(str(c).zfill(6) for c in holding_codes)
    cached_codes = sorted(str(c).zfill(6) for c in payload.get("holding_codes", []))
    if cached_codes != expected_codes:
        return None

    generated_at = _parse_date(payload.get("generated_at"))
    if not generated_at:
        return None
    if (today - generated_at).days < 0 or (today - generated_at).days > max_age_days:
        return None

    funds = payload.get("funds") or {}
    for code in expected_codes:
        keywords = (funds.get(code) or {}).get("keywords") or []
        if not keywords:
            return None
    return payload


def build_keyword_request(config, analyzer, report_date: date) -> Dict[str, Any]:
    funds = []
    for holding in config.holdings:
        code = str(holding.code).zfill(6)
        fund_data = getattr(analyzer, "funds", {}).get(code, {}) if analyzer else {}
        basic = fund_data.get("basic", {}) or {}
        fund_type = _string_value(getattr(holding, "type", "") or basic.get("fund_type", ""))
        name = getattr(holding, "name", "") or basic.get("name", code)
        funds.append({
            "fund_code": code,
            "fund_name": name,
            "fund_type": fund_type,
            "theme": _infer_theme(name, fund_type),
            "style_tags": _infer_style_tags(name, fund_type),
            "top_holdings": _holding_rows(fund_data.get("holdings")),
            "sectors": _sector_rows(fund_data.get("sectors")),
            "expected_cache_entry": {
                "keywords": ["重仓公司、产业链、政策、资金、估值关键词"],
                "research_lenses": ["这些关键词为什么会影响该基金净值"],
                "tags": ["主题或风险标签"],
                "rationale": "基于重仓、行业和基金类型的推导说明",
            },
        })

    holding_codes = sorted(str(h.code).zfill(6) for h in config.holdings)
    return {
        "request_version": REQUEST_VERSION,
        "generated_at": report_date.isoformat() if hasattr(report_date, "isoformat") else str(report_date),
        "instructions": [
            "请基于每只基金的真实重仓、行业、基金类型和主题标签，为新闻搜索生成关键词缓存。",
            "输出必须写入 news_keyword_profiles.json 结构，cache_version 为 news_keyword_profiles.v1。",
            "每只基金给出 5-12 个高价值关键词，优先公司、产业链、政策、资金、估值和风险事件词。",
            "不要只使用基金名称里的宽泛行业词；数据缺失时在 rationale 中说明。",
        ],
        "holding_codes": holding_codes,
        "funds": funds,
        "expected_cache_schema": {
            "cache_version": CACHE_VERSION,
            "generated_at": report_date.isoformat() if hasattr(report_date, "isoformat") else str(report_date),
            "holding_codes": holding_codes,
            "funds": {
                "基金代码": {
                    "keywords": ["关键词1", "关键词2"],
                    "research_lenses": ["分析视角"],
                    "tags": ["主题标签"],
                    "rationale": "生成理由",
                }
            },
        },
    }


def write_keyword_request(path: str, request: Dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(request, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _holding_rows(df) -> List[Dict[str, Any]]:
    rows = []
    if df is None or getattr(df, "empty", True):
        return rows
    for _, row in df.head(10).iterrows():
        rows.append({
            "stock_code": _pick(row, ["股票代码", "代码", "stock_code"]),
            "stock_name": _pick(row, ["股票名称", "名称", "stock_name"]),
            "weight": _pick(row, ["占净值比例", "持仓占比", "占比", "weight"]),
        })
    return rows


def _sector_rows(df) -> List[Dict[str, Any]]:
    rows = []
    if df is None or getattr(df, "empty", True):
        return rows
    for _, row in df.head(10).iterrows():
        rows.append({
            "sector": _pick(row, ["行业", "行业名称", "sector"]),
            "weight": _pick(row, ["占比", "占净值比例", "weight"]),
        })
    return rows


def _pick(row, names: List[str]) -> str:
    for name in names:
        if name in row and row.get(name) is not None:
            value = str(row.get(name)).strip()
            if value and value.lower() != "nan":
                return value
    return ""


def _infer_theme(name: str, fund_type: str) -> str:
    try:
        from src.recommend.engine import infer_theme
        return infer_theme(name, fund_type)
    except Exception:
        return ""


def _infer_style_tags(name: str, fund_type: str) -> List[str]:
    try:
        from src.recommend.engine import infer_style_tags
        return infer_style_tags(name, fund_type)
    except Exception:
        return []


def _string_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")
