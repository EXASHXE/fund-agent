"""Workflow evidence bridge — converts fund_analysis output and host evidence
into an EvidenceGraph for decision_support tests and host examples.

This module is deterministic. It does not call network, MCP, or LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


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


def build_evidence_graph_from_workflow(
    *,
    fund_analysis_output: dict[str, Any] | None = None,
    host_news_evidence: list[dict[str, Any]] | None = None,
    host_sentiment_evidence: list[dict[str, Any]] | None = None,
    host_benchmark_evidence: list[dict[str, Any]] | None = None,
    host_fee_evidence: list[dict[str, Any]] | None = None,
    host_redemption_evidence: list[dict[str, Any]] | None = None,
    include_diagnostics: bool = True,
) -> WorkflowEvidenceGraphResult:
    """Convert fund_analysis output and host evidence into an EvidenceGraph.

    Args:
        fund_analysis_output: Dict from SkillOutput.to_dict() of fund_analysis.
        host_news_evidence: Raw news items from host (e.g. from MCP).
        host_sentiment_evidence: Raw sentiment items from host.
        host_benchmark_evidence: Benchmark-related evidence from host.
        host_fee_evidence: Fee schedule evidence from host.
        host_redemption_evidence: Redemption rule evidence from host.
        include_diagnostics: Whether to include diagnostic artifacts as evidence.

    Returns:
        WorkflowEvidenceGraphResult with the graph and diagnostic metadata.
    """
    graph = EvidenceGraph()
    missing_or_invalid: list[dict[str, Any]] = []
    warnings: list[str] = []
    host_soft_count = 0

    _ingest_fund_analysis_evidence(graph, fund_analysis_output, missing_or_invalid)
    host_soft_count += _ingest_host_soft_evidence(
        graph, convert_host_news_to_soft_evidence, host_news_evidence or [],
        "news", missing_or_invalid, warnings,
    )
    host_soft_count += _ingest_host_soft_evidence(
        graph, convert_host_sentiment_to_soft_evidence, host_sentiment_evidence or [],
        "sentiment", missing_or_invalid, warnings,
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
            evidence_item = converter(raw_item)
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
    for k, v in summary.items():
        if isinstance(v, (bool, str, int, float)):
            claim_parts.append(f"{k}:{v}")
    claim = f"{artifact_key}: " + (", ".join(claim_parts) if claim_parts else "diagnostic present")

    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        evidence_type="HardEvidence",
        source_type=source_label,
        timestamp=datetime.now(timezone.utc),
        related_entities=related if related else ["unknown_fund"],
        claim=claim[:500],
        value=artifact,
        confidence_weight=1.0,
        direction="neutral",
        provenance={"artifact_key": artifact_key},
    )


def convert_host_news_to_soft_evidence(news_item: dict[str, Any]) -> EvidenceItem | None:
    """Convert a host-provided news item into SoftEvidence.

    Args:
        news_item: Dict with at minimum 'title' or 'claim' and 'entities'.
            Optional: 'direction', 'confidence', 'source', 'timestamp'.

    Returns:
        EvidenceItem or None if the input is invalid.
    """
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

    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        evidence_type="SoftEvidence",
        source_type=source,
        timestamp=_parse_timestamp(news_item.get("timestamp")) or datetime.now(timezone.utc),
        related_entities=list(entities),
        claim=str(title)[:500],
        value=news_item,
        confidence_weight=confidence,
        direction=str(direction),
        provenance={"origin": "host_news"},
    )


def convert_host_sentiment_to_soft_evidence(sentiment_item: dict[str, Any]) -> EvidenceItem | None:
    """Convert a host-provided sentiment item into SoftEvidence.

    Args:
        sentiment_item: Dict with at minimum 'entity' or 'entities',
            and 'sentiment' or 'score'.

    Returns:
        EvidenceItem or None if the input is invalid.
    """
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

    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        evidence_type="SoftEvidence",
        source_type=source,
        timestamp=_parse_timestamp(sentiment_item.get("timestamp")) or datetime.now(timezone.utc),
        related_entities=list(entities),
        claim=str(claim)[:500],
        value=sentiment_item,
        confidence_weight=confidence,
        direction=str(direction),
        provenance={"origin": "host_sentiment"},
    )


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
        ts = datetime.now(timezone.utc)

    return EvidenceItem(
        evidence_id=str(raw.get("evidence_id", str(uuid.uuid4()))),
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
