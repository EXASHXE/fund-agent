"""Shared helpers for decision_support golden regression snapshots.

These helpers are test/tooling only. They call the existing runtime bridge CLI
as a subprocess and normalize the bridge envelope without importing runtime
skill classes or provider SDKs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = ROOT / "scripts" / "run_skill.py"
GOLDEN_ROOT = ROOT / "tests" / "golden"
JSON_SNAPSHOT_DIR = GOLDEN_ROOT / "decision_support"

UPDATE_COMMAND = "python scripts/update_decision_support_golden.py"

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
    "created_at": "<normalized-timestamp>",
    "generated_at": "<normalized-timestamp>",
    "decision_id": "<normalized-decision-id>",
    "ledger_id": "<normalized-ledger-id>",
}


@dataclass(frozen=True)
class GoldenFixture:
    """One decision_support fixture and its golden snapshot file name."""

    input_path: str
    snapshot_name: str

    @property
    def absolute_input_path(self) -> Path:
        return ROOT / self.input_path

    @property
    def json_snapshot_path(self) -> Path:
        return JSON_SNAPSHOT_DIR / self.snapshot_name


DECISION_SUPPORT_GOLDEN_FIXTURES: tuple[GoldenFixture, ...] = (
    GoldenFixture(
        "examples/decision_support/single_active_buy_with_evidence.json",
        "single_active_buy_with_evidence.json",
    ),
    GoldenFixture(
        "examples/decision_support/single_passive_hold_without_evidence.json",
        "single_passive_hold_without_evidence.json",
    ),
    GoldenFixture(
        "examples/decision_support/trade_plan_selected_trade_with_caps.json",
        "trade_plan_selected_trade_with_caps.json",
    ),
    GoldenFixture(
        "examples/decision_support/trade_plan_no_evidence_downgraded.json",
        "trade_plan_no_evidence_downgraded.json",
    ),
)


def run_decision_support_json(fixture: GoldenFixture) -> dict[str, Any]:
    """Run a fixture through the runtime bridge and return parsed JSON."""
    proc = _run_bridge([
        "--skill",
        "decision_support",
        "--input",
        fixture.input_path,
        "--pretty",
    ])
    if proc.returncode != 0:
        raise RuntimeError(
            f"runtime bridge JSON run failed for {fixture.input_path}: "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return json.loads(proc.stdout)


def normalize_bridge_json(envelope: dict[str, Any]) -> dict[str, Any]:
    """Normalize a runtime bridge JSON envelope for golden comparisons.

    Keeps externally relevant fields and drops volatile bridge/process details
    such as step IDs, manifest paths, generated UUIDs, and timestamps.
    Object keys are sorted recursively; list order is preserved.
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


def _run_bridge(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(BRIDGE_SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


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
