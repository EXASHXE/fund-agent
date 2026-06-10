"""Shared helpers for fund_analysis golden regression snapshots.

These helpers are test/tooling only. They call the existing runtime bridge
in-process and normalize the bridge envelope without importing runtime
skill classes or provider SDKs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = ROOT / "tests" / "golden"
JSON_SNAPSHOT_DIR = GOLDEN_ROOT / "fund_analysis"
MARKDOWN_SNAPSHOT_DIR = GOLDEN_ROOT / "fund_analysis_markdown"

UPDATE_COMMAND = "python scripts/update_fund_analysis_golden.py"

FORMAL_DECISION_ARTIFACTS = {
    "decision",
    "decisions",
    "execution_ledger",
    "execution_ledgers",
}


@dataclass(frozen=True)
class GoldenFixture:
    """One fund_analysis fixture and its golden snapshot file names."""

    input_path: str
    snapshot_name: str
    markdown_snapshot: bool

    @property
    def absolute_input_path(self) -> Path:
        return ROOT / self.input_path

    @property
    def json_snapshot_path(self) -> Path:
        return JSON_SNAPSHOT_DIR / self.snapshot_name

    @property
    def markdown_snapshot_path(self) -> Path:
        return MARKDOWN_SNAPSHOT_DIR / self.snapshot_name.replace(".json", ".md")


FUND_ANALYSIS_GOLDEN_FIXTURES: tuple[GoldenFixture, ...] = (
    GoldenFixture(
        "examples/runtime_bridge_fund_analysis_input.json",
        "runtime_bridge_fund_analysis_input.json",
        False,
    ),
    GoldenFixture(
        "examples/runtime_bridge_personal_report_quality_input.json",
        "runtime_bridge_personal_report_quality_input.json",
        True,
    ),
    GoldenFixture(
        "examples/scenarios/cn_fund_7d_redemption_fee.json",
        "cn_fund_7d_redemption_fee.json",
        True,
    ),
    GoldenFixture(
        "examples/scenarios/cn_fund_qdii_sp500_overlap.json",
        "cn_fund_qdii_sp500_overlap.json",
        True,
    ),
    GoldenFixture(
        "examples/scenarios/cn_fund_ai_semiconductor_overweight.json",
        "cn_fund_ai_semiconductor_overweight.json",
        True,
    ),
    GoldenFixture(
        "examples/scenarios/cn_fund_dca_drawdown_review.json",
        "cn_fund_dca_drawdown_review.json",
        True,
    ),
    GoldenFixture(
        "examples/scenarios/cn_fund_ledger_derived_snapshot.json",
        "cn_fund_ledger_derived_snapshot.json",
        True,
    ),
)


TOP_LEVEL_KEYS = (
    "ok",
    "skill_name",
    "status",
    "artifacts",
    "evidence_items",
    "warnings",
    "errors",
    "used_mcp_capabilities",
)

METADATA_KEYS = (
    "required_mcp_capabilities",
    "missing_mcp_capabilities",
)

VOLATILE_VALUE_KEYS = {
    "evidence_id": "<normalized-evidence-id>",
    "timestamp": "<normalized-timestamp>",
}


def run_fund_analysis_json(fixture: GoldenFixture) -> dict[str, Any]:
    """Run a fixture through the runtime bridge in-process and return parsed JSON."""
    from tests.support.bridge_runner import run_bridge_inprocess_json

    input_text = fixture.absolute_input_path.read_text(encoding="utf-8")
    return run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text, pretty=True)


def run_fund_analysis_markdown(fixture: GoldenFixture) -> str:
    """Run a fixture through the explicit Markdown report bridge mode in-process."""
    from tests.support.bridge_runner import run_bridge_inprocess_text

    input_text = fixture.absolute_input_path.read_text(encoding="utf-8")
    raw = run_bridge_inprocess_text(skill="fund_analysis", input_text=input_text, emit_report="markdown")
    return normalize_markdown(raw)


def normalize_bridge_json(envelope: dict[str, Any]) -> dict[str, Any]:
    """Normalize a runtime bridge JSON envelope for golden comparisons.

    The normalized snapshot keeps externally relevant skill behavior and drops
    bridge/process details such as step IDs, manifest paths, and runtime import
    paths. Object keys are sorted recursively; list order is preserved.
    """
    normalized: dict[str, Any] = {}
    for key in TOP_LEVEL_KEYS:
        if key in envelope:
            normalized[key] = _normalize_value(envelope[key])

    metadata = envelope.get("metadata")
    if isinstance(metadata, dict):
        kept_metadata = {
            key: _normalize_value(metadata[key])
            for key in METADATA_KEYS
            if key in metadata
        }
        if kept_metadata:
            normalized["metadata"] = _sort_mapping(kept_metadata)

    return _sort_mapping(normalized)


def serialize_snapshot(data: dict[str, Any]) -> str:
    """Serialize a normalized JSON snapshot deterministically."""
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def normalize_markdown(text: str) -> str:
    """Normalize Markdown line endings and trailing newline only."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip("\n") + "\n"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sort_mapping({
            str(key): (
                VOLATILE_VALUE_KEYS[str(key)]
                if str(key) in VOLATILE_VALUE_KEYS
                else _normalize_value(item)
            )
            for key, item in value.items()
        })
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _sort_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in sorted(value)}
