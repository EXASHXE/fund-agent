"""Workflow evidence bridge — converts fund_analysis output and host evidence
into an EvidenceGraph for decision_support tests and host examples.

This module is deterministic. It does not call network, MCP, or LLM.
Evidence IDs are stable hashes of content, not random UUIDs.
Timestamps are derived from host payload, not wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


FROZEN_TIMESTAMP = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "broker_order_id",
    "order_id",
    "order_status",
    "filled_quantity",
    "fill_price",
    "execution_venue",
    "submitted_at",
    "broker",
    "exchange_order_id",
})

SOURCE_TYPE_ALIAS_MAP: dict[str, str] = {
    "portfolio_allocation_concentration": "portfolio_analysis",
    "fund_risk_return_metrics": "quant_tool",
    "portfolio_risk_flags": "risk_detection",
    "portfolio_pnl_summary": "pnl_calculation",
    "fee_schedule": "fee_schedule",
    "redemption_rules": "redemption_rules",
    "benchmark_history": "benchmark_history",
    "host_news": "host_news",
    "host_sentiment": "host_sentiment",
    "right_side": "right_side",
    "cash_deployment": "cash_deployment",
    "profit_protection": "profit_protection",
    "benchmark_divergence": "benchmark_divergence",
    "event_hype": "event_hype",
    "evidence_gap": "evidence_gap",
    "redemption_fee": "redemption_fee",
    "position_contribution": "position_contribution",
}


@dataclass
class WorkflowEvidenceGraphResult:
    """Result of building an EvidenceGraph from workflow outputs."""

    graph: EvidenceGraph
    included_evidence_count: int
    host_soft_evidence_count: int
    missing_or_invalid_evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_dict(),
            "included_evidence_count": self.included_evidence_count,
            "host_soft_evidence_count": self.host_soft_evidence_count,
            "missing_or_invalid_evidence": self.missing_or_invalid_evidence,
            "warnings": self.warnings,
        }


def _stable_evidence_id(prefix: str, payload: dict[str, Any]) -> str:
    """Produce a deterministic evidence_id from content hash."""
    key_material = json.dumps({
        "prefix": prefix,
        "source": payload.get("source", payload.get("source_type", "")),
        "entities": sorted(payload.get("entities", payload.get("related_entities", []))),
        "claim": payload.get("claim", payload.get("title", "")),
        "value": _normalize_value(payload.get("value", payload)),
    }, sort_keys=True, default=str)
    digest = hashlib.sha256(key_material.encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _stable_timestamp(raw_item: dict[str, Any], fallback_as_of_date: str | None = None) -> datetime:
    """Produce a deterministic timestamp from host data or fallback.

    Rules:
    - If host item has timestamp/date/as_of_date, parse it.
    - Else if fallback_as_of_date is provided, use it at 00:00:00 UTC.
    - Else use 1970-01-01T00:00:00+00:00.
    """
    for key in ("timestamp", "date", "as_of_date"):
        ts = raw_item.get(key)
        if ts:
            parsed = _parse_timestamp(ts)
            if parsed:
                return parsed

    if fallback_as_of_date:
        parsed = _parse_timestamp(fallback_as_of_date)
        if parsed:
            return parsed.replace(hour=0, minute=0, second=0, microsecond=0)

    return FROZEN_TIMESTAMP


def _normalize_value(value: Any) -> str:
    """Normalize a value for stable hashing."""
    if value is None:
        return "__none__"
    if isinstance(value, (int, float, str, bool)):
        return str(value)
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)[:200]


def _extract_as_of_date(fund_analysis_output: dict[str, Any] | None) -> str | None:
    """Extract as_of_date from fund_analysis output or nested portfolio."""
    if not fund_analysis_output:
        return None
    portfolio = fund_analysis_output.get("portfolio") or fund_analysis_output.get("payload", {}).get("portfolio", {})
    if isinstance(portfolio, dict):
        return portfolio.get("as_of_date")
    artifacts = fund_analysis_output.get("artifacts", {})
    if isinstance(artifacts, dict):
        ps = artifacts.get("portfolio_summary", {})
        if isinstance(ps, dict):
            return ps.get("as_of_date")
    return None


def build_evidence_graph_from_workflow(
    *,
    fund_analysis_output: dict[str, Any] | None = None,
    host_news_evidence: list[dict[str, Any]] | None = None,
    host_sentiment_evidence: list[dict[str, Any]] | None = None,
    host_benchmark_evidence: Any = None,
    host_fee_evidence: Any = None,
    host_redemption_evidence: Any = None,
    include_diagnostics: bool = True,
) -> WorkflowEvidenceGraphResult:
    """Convert fund_analysis output and host evidence into an EvidenceGraph.

    Args:
        fund_analysis_output: Dict from SkillOutput.to_dict() of fund_analysis.
        host_news_evidence: Raw news items from host (list of dicts).
        host_sentiment_evidence: Raw sentiment items from host (list of dicts).
        host_benchmark_evidence: Benchmark data (list[dict] or dict keyed by fund_code).
        host_fee_evidence: Fee schedule data (list[dict] or dict keyed by fund_code).
        host_redemption_evidence: Redemption rules (list[dict] or dict keyed by fund_code).
        include_diagnostics: Whether to include diagnostic artifacts as evidence.

    Returns:
        WorkflowEvidenceGraphResult with the graph and diagnostic metadata.
    """
    graph = EvidenceGraph()
    missing_or_invalid: list[dict[str, Any]] = []
    warnings: list[str] = []
    host_soft_count = 0
    as_of_date = _extract_as_of_date(fund_analysis_output)

    _ingest_fund_analysis_evidence(graph, fund_analysis_output, missing_or_invalid)

    host_soft_count += _ingest_host_soft_evidence(
        graph, convert_host_news_to_soft_evidence, host_news_evidence or [],
        "news", missing_or_invalid, warnings, as_of_date,
    )
    host_soft_count += _ingest_host_soft_evidence(
        graph, convert_host_sentiment_to_soft_evidence, host_sentiment_evidence or [],
        "sentiment", missing_or_invalid, warnings, as_of_date,
    )

    _ingest_hard_evidence(
        graph, convert_host_benchmark_to_hard_evidence, host_benchmark_evidence or [],
        "benchmark_history", missing_or_invalid, warnings, as_of_date,
    )
    _ingest_hard_evidence(
        graph, convert_host_fee_to_hard_evidence, host_fee_evidence or [],
        "fee_schedule", missing_or_invalid, warnings, as_of_date,
    )
    _ingest_hard_evidence(
        graph, convert_host_redemption_to_hard_evidence, host_redemption_evidence or [],
        "redemption_rules", missing_or_invalid, warnings, as_of_date,
    )

    if include_diagnostics:
        _ingest_diagnostic_evidence(
            graph, fund_analysis_output, missing_or_invalid, warnings,
        )

    included_count = len(graph.items)

    result = WorkflowEvidenceGraphResult(
        graph=graph,
        included_evidence_count=included_count,
        host_soft_evidence_count=host_soft_count,
        missing_or_invalid_evidence=missing_or_invalid,
        warnings=warnings,
    )

    _validate_no_execution_fields(result.to_dict())
    return result


def resolve_evidence_source_refs(
    trade_plan: dict[str, Any],
    evidence_graph: EvidenceGraph,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve evidence_source_refs to actual graph evidence_ids.

    Maps source_type aliases (e.g. "benchmark_history", "host_news")
    to matching EvidenceGraph items by source_type. Returns updated
    trade_plan and list of warnings for unresolved refs.

    Args:
        trade_plan: Trade plan dict with suggested_trade_plan list.
        evidence_graph: Compiled EvidenceGraph.

    Returns:
        (updated_trade_plan, unresolved_warnings) tuple.
    """
    unresolved_warnings: list[str] = []

    source_index: dict[str, list[str]] = {}
    for eid, item in evidence_graph.items.items():
        source_key = str(item.source_type or "")
        source_index.setdefault(source_key, []).append(eid)

    suggested = trade_plan.get("suggested_trade_plan", [])
    if not isinstance(suggested, list):
        return trade_plan, unresolved_warnings

    updated_trades = []
    for trade in suggested:
        if not isinstance(trade, dict):
            updated_trades.append(trade)
            continue

        t = dict(trade)
        source_refs = t.get("evidence_source_refs", [])
        if not isinstance(source_refs, list) or not source_refs:
            updated_trades.append(t)
            continue

        resolved_ids = []
        for ref in source_refs:
            ref_str = str(ref)
            alias = SOURCE_TYPE_ALIAS_MAP.get(ref_str, ref_str)
            matches = source_index.get(alias, source_index.get(ref_str, []))
            if matches:
                resolved_ids.append(matches[0])
            else:
                unresolved_warnings.append(
                    f"Unresolved evidence_source_ref '{ref_str}' for trade {t.get('trade_id', '')}"
                )

        if resolved_ids:
            t["evidence_refs"] = list(t.get("evidence_refs", [])) + resolved_ids
        updated_trades.append(t)

    updated_plan = dict(trade_plan)
    updated_plan["suggested_trade_plan"] = updated_trades
    return updated_plan, unresolved_warnings


def _ingest_fund_analysis_evidence(
    graph: EvidenceGraph,
    fund_analysis_output: dict[str, Any] | None,
    missing_or_invalid: list[dict[str, Any]],
) -> None:
    if not fund_analysis_output:
        return

    raw_evidence = fund_analysis_output.get("evidence_items", [])
    if not isinstance(raw_evidence, list):
        missing_or_invalid.append({"issue": "evidence_items is not a list"})
        return

    for item_dict in raw_evidence:
        if not isinstance(item_dict, dict):
            missing_or_invalid.append({"issue": "evidence item is not a dict"})
            continue
        try:
            evidence_item = _evidence_item_from_raw(item_dict)
            graph.add(evidence_item)
        except Exception as exc:
            missing_or_invalid.append({
                "evidence_id": item_dict.get("evidence_id", "unknown"),
                "error": str(exc),
            })


def _ingest_host_soft_evidence(
    graph: EvidenceGraph,
    converter,
    raw_items: list[dict[str, Any]],
    source_label: str,
    missing_or_invalid: list[dict[str, Any]],
    warnings: list[str],
    as_of_date: str | None = None,
) -> int:
    count = 0
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            missing_or_invalid.append({
                "source_type": source_label,
                "issue": "item is not a dict",
            })
            warnings.append(f"Invalid {source_label} item: not a dict")
            continue
        try:
            evidence_item = converter(raw_item, as_of_date=as_of_date)
            if evidence_item is not None:
                graph.add(evidence_item)
                count += 1
            else:
                missing_or_invalid.append({
                    "source_type": source_label,
                    "issue": "converter returned None (missing required fields)",
                    "item_snippet": str(raw_item)[:200],
                })
                warnings.append(f"Failed to convert {source_label} item: missing required fields")
        except Exception as exc:
            missing_or_invalid.append({
                "source_type": source_label,
                "item_snippet": str(raw_item)[:200],
                "error": str(exc),
            })
            warnings.append(f"Failed to convert {source_label} item: {exc}")

    if not raw_items:
        warnings.append(f"No {source_label} evidence provided by host")

    return count


def _ingest_hard_evidence(
    graph: EvidenceGraph,
    converter,
    raw_data: Any,
    source_label: str,
    missing_or_invalid: list[dict[str, Any]],
    warnings: list[str],
    as_of_date: str | None = None,
) -> int:
    """Ingest hard evidence (benchmark, fee, redemption) in any shape."""
    items = _normalize_to_item_list(raw_data, source_label)
    count = 0
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        try:
            evidence_item = converter(raw_item, as_of_date=as_of_date)
            if evidence_item is not None:
                graph.add(evidence_item)
                count += 1
        except Exception as exc:
            missing_or_invalid.append({
                "source_type": source_label,
                "item_snippet": str(raw_item)[:200],
                "error": str(exc),
            })
    return count


def _normalize_to_item_list(raw: Any, source_label: str) -> list[dict[str, Any]]:
    """Accept list[dict], dict keyed by fund_code, or dict with items/list fields."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "items" in raw and isinstance(raw["items"], list):
            return raw["items"]
        if source_label in raw and isinstance(raw[source_label], list):
            return raw[source_label]
        items = []
        for key, value in raw.items():
            if isinstance(value, dict) and key not in ("items", source_label):
                item = dict(value)
                item.setdefault("fund_code", key)
                items.append(item)
            elif isinstance(value, list):
                for elem in value:
                    if isinstance(elem, dict):
                        items.append(elem)
        return items
    return []


def _ingest_diagnostic_evidence(
    graph: EvidenceGraph,
    fund_analysis_output: dict[str, Any] | None,
    missing_or_invalid: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    """Convert fund_analysis diagnostic artifacts into HardEvidence items."""
    if not fund_analysis_output:
        return

    artifacts = fund_analysis_output.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return

    diagnostic_map = {
        "profit_protection_diagnostics": "profit_protection",
        "benchmark_divergence_diagnostics": "benchmark_divergence",
        "right_side_confirmation_diagnostics": "right_side",
        "event_hype_failure_diagnostics": "event_hype",
        "cash_deployment_diagnostics": "cash_deployment",
        "evidence_gap_diagnostics": "evidence_gap",
        "redemption_fee_risk": "redemption_fee",
    }

    for artifact_key, source_label in diagnostic_map.items():
        value = artifacts.get(artifact_key)
        if value and isinstance(value, dict):
            try:
                diag = _build_diagnostic_hard_evidence(value, artifact_key, source_label)
                if diag:
                    graph.add(diag)
            except Exception:
                pass


def _build_diagnostic_hard_evidence(
    artifact: dict[str, Any],
    artifact_key: str,
    source_label: str,
) -> EvidenceItem | None:
    if not artifact:
        return None

    related = list(artifact.get("fund_codes", []))
    if not related:
        summary = artifact.get("summary", {})
        related = list(summary.get("fund_codes", []))

    claim_parts = []
    summary = artifact.get("summary", {})
    if isinstance(summary, dict):
        for k, v in sorted(summary.items()):
            if isinstance(v, (bool, str, int, float)):
                claim_parts.append(f"{k}:{v}")
    claim = f"{artifact_key}: " + (", ".join(claim_parts) if claim_parts else "diagnostic present")

    entities = related if related else ["unknown_fund"]
    uid = _stable_evidence_id("diag", {
        "source_type": source_label,
        "entities": entities,
        "claim": claim,
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="HardEvidence",
        source_type=source_label,
        timestamp=FROZEN_TIMESTAMP,
        related_entities=entities,
        claim=claim[:500],
        value=artifact,
        confidence_weight=1.0,
        direction="neutral",
        provenance={"artifact_key": artifact_key},
    )


# ── Host evidence converters ────────────────────────────────────────────────


def convert_host_news_to_soft_evidence(
    news_item: dict[str, Any],
    as_of_date: str | None = None,
) -> EvidenceItem | None:
    if not isinstance(news_item, dict):
        return None

    title = news_item.get("title", news_item.get("claim", ""))
    if not title:
        return None

    entities = news_item.get("entities", news_item.get("related_entities", []))
    if isinstance(entities, str):
        entities = [entities]
    if not entities:
        return None

    direction = news_item.get("direction", "neutral")
    confidence = float(news_item.get("confidence", news_item.get("confidence_weight", 0.5)))
    confidence = min(max(confidence, 0.1), 0.9)
    source = news_item.get("source", "host_news")
    ts = _stable_timestamp(news_item, as_of_date)
    uid = _stable_evidence_id("news", {
        "source_type": source,
        "entities": list(entities),
        "claim": str(title),
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="SoftEvidence",
        source_type=source,
        timestamp=ts,
        related_entities=list(entities),
        claim=str(title)[:500],
        value=news_item,
        confidence_weight=confidence,
        direction=str(direction),
        provenance={"origin": "host_news"},
    )


def convert_host_sentiment_to_soft_evidence(
    sentiment_item: dict[str, Any],
    as_of_date: str | None = None,
) -> EvidenceItem | None:
    if not isinstance(sentiment_item, dict):
        return None

    entities = sentiment_item.get("entities", sentiment_item.get("related_entities", []))
    if isinstance(entities, str):
        entities = [entities]
    single = sentiment_item.get("entity")
    if single and not entities:
        entities = [single]
    if not entities:
        return None

    score = sentiment_item.get("sentiment", sentiment_item.get("score", 0))
    try:
        score_f = float(score)
    except (TypeError, ValueError):
        score_f = 0.0

    if score_f > 0:
        direction = "positive"
    elif score_f < 0:
        direction = "negative"
    else:
        direction = "neutral"

    confidence = float(sentiment_item.get("confidence", sentiment_item.get("confidence_weight", 0.5)))
    confidence = min(max(confidence, 0.1), 0.9)
    source = sentiment_item.get("source", "host_sentiment")
    claim = sentiment_item.get("claim", sentiment_item.get("title", f"Sentiment score: {score_f}"))
    ts = _stable_timestamp(sentiment_item, as_of_date)
    uid = _stable_evidence_id("sent", {
        "source_type": source,
        "entities": list(entities),
        "claim": str(claim),
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="SoftEvidence",
        source_type=source,
        timestamp=ts,
        related_entities=list(entities),
        claim=str(claim)[:500],
        value=sentiment_item,
        confidence_weight=confidence,
        direction=str(direction),
        provenance={"origin": "host_sentiment"},
    )


def convert_host_benchmark_to_hard_evidence(
    item: dict[str, Any],
    as_of_date: str | None = None,
) -> EvidenceItem | None:
    if not isinstance(item, dict):
        return None

    fund_code = item.get("fund_code", "")
    entities = [fund_code] if fund_code else item.get("entities", item.get("related_entities", []))
    if isinstance(entities, str):
        entities = [entities]
    if not entities:
        return None

    source = item.get("source", "benchmark_history")
    claim = item.get("claim", f"Benchmark data for {entities[0]}")
    ts = _stable_timestamp(item, as_of_date)
    uid = _stable_evidence_id("bm", {
        "source_type": source,
        "entities": list(entities),
        "claim": str(claim),
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="HardEvidence",
        source_type=source,
        timestamp=ts,
        related_entities=list(entities),
        claim=str(claim)[:500],
        value=item,
        confidence_weight=1.0,
        direction="neutral",
        provenance={"origin": "host_benchmark"},
    )


def convert_host_fee_to_hard_evidence(
    item: dict[str, Any],
    as_of_date: str | None = None,
) -> EvidenceItem | None:
    if not isinstance(item, dict):
        return None

    fund_code = item.get("fund_code", "")
    entities = [fund_code] if fund_code else item.get("entities", item.get("related_entities", []))
    if isinstance(entities, str):
        entities = [entities]
    if not entities:
        return None

    source = item.get("source", "fee_schedule")
    claim = item.get("claim", f"Fee schedule for {entities[0]}")
    ts = _stable_timestamp(item, as_of_date)
    uid = _stable_evidence_id("fee", {
        "source_type": source,
        "entities": list(entities),
        "claim": str(claim),
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="HardEvidence",
        source_type=source,
        timestamp=ts,
        related_entities=list(entities),
        claim=str(claim)[:500],
        value=item,
        confidence_weight=1.0,
        direction="neutral",
        provenance={"origin": "host_fee"},
    )


def convert_host_redemption_to_hard_evidence(
    item: dict[str, Any],
    as_of_date: str | None = None,
) -> EvidenceItem | None:
    if not isinstance(item, dict):
        return None

    fund_code = item.get("fund_code", "")
    entities = [fund_code] if fund_code else item.get("entities", item.get("related_entities", []))
    if isinstance(entities, str):
        entities = [entities]
    if not entities:
        return None

    source = item.get("source", "redemption_rules")
    claim = item.get("claim", f"Redemption rules for {entities[0]}")
    ts = _stable_timestamp(item, as_of_date)
    uid = _stable_evidence_id("red", {
        "source_type": source,
        "entities": list(entities),
        "claim": str(claim),
    })

    return EvidenceItem(
        evidence_id=uid,
        evidence_type="HardEvidence",
        source_type=source,
        timestamp=ts,
        related_entities=list(entities),
        claim=str(claim)[:500],
        value=item,
        confidence_weight=1.0,
        direction="neutral",
        provenance={"origin": "host_redemption"},
    )


# ── Utility helpers ─────────────────────────────────────────────────────────


def _parse_timestamp(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def _evidence_item_from_raw(raw: dict[str, Any]) -> EvidenceItem:
    ts = raw.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif isinstance(ts, datetime):
        pass
    else:
        ts = FROZEN_TIMESTAMP

    evidence_id = str(raw.get("evidence_id", ""))
    if not evidence_id:
        evidence_id = _stable_evidence_id("fa", raw)

    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=str(raw.get("evidence_type", "HardEvidence")),
        source_type=str(raw.get("source_type", "")) or "unknown",
        timestamp=ts,
        related_entities=_ensure_list(raw.get("related_entities", [])),
        claim=str(raw.get("claim", ""))[:500],
        value=raw.get("value"),
        confidence_weight=float(raw.get("confidence_weight", 1.0)),
        direction=str(raw.get("direction", "neutral")),
        provenance=dict(raw.get("provenance", {})),
    )


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return []


# ── Execution field validation ──────────────────────────────────────────────


def _validate_no_execution_fields(data: dict[str, Any]) -> None:
    """Ensure no broker/order execution fields exist in output."""
    found = _find_forbidden_fields(data, path="")
    if found:
        raise ValueError(
            f"Forbidden broker/order execution fields found: {found}"
        )


def _find_forbidden_fields(data: Any, path: str) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in FORBIDDEN_EXECUTION_FIELDS:
                found.append(f"{path}.{key}" if path else key)
            if isinstance(value, (dict, list)):
                new_path = f"{path}.{key}" if path else key
                found.extend(_find_forbidden_fields(value, new_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                found.extend(_find_forbidden_fields(item, f"{path}[{i}]"))
    return found
