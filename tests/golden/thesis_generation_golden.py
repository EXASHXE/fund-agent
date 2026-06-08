"""Shared helpers for thesis_generation golden regression snapshots."""

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
JSON_SNAPSHOT_DIR = GOLDEN_ROOT / "thesis_generation"

UPDATE_COMMAND = "python scripts/update_thesis_generation_golden.py"

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

VOLATILE_VALUE_KEYS = {
    "task_id": "<normalized-task-id>",
    "step_id": "<normalized-step-id>",
    "evidence_id": "<normalized-evidence-id>",
    "timestamp": "<normalized-timestamp>",
}


@dataclass(frozen=True)
class GoldenFixture:
    input_path: str
    snapshot_name: str

    @property
    def absolute_input_path(self) -> Path:
        return ROOT / self.input_path

    @property
    def json_snapshot_path(self) -> Path:
        return JSON_SNAPSHOT_DIR / self.snapshot_name


THESIS_GENERATION_GOLDEN_FIXTURES: tuple[GoldenFixture, ...] = (
    GoldenFixture(
        "examples/thesis_generation/thesis_with_mixed_evidence.json",
        "thesis_with_mixed_evidence.json",
    ),
    GoldenFixture(
        "examples/thesis_generation/thesis_from_fund_analysis_artifacts.json",
        "thesis_from_fund_analysis_artifacts.json",
    ),
    GoldenFixture(
        "examples/thesis_generation/thesis_missing_evidence_partial.json",
        "thesis_missing_evidence_partial.json",
    ),
)


def run_thesis_generation_json(fixture: GoldenFixture) -> dict[str, Any]:
    proc = _run_bridge([
        "--skill",
        "thesis_generation",
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
    normalized: dict[str, Any] = {}
    for key in TOP_LEVEL_KEYS:
        if key in envelope:
            normalized[key] = _normalize_value(envelope[key])
    return _sort_mapping(normalized)


def serialize_snapshot(data: dict[str, Any]) -> str:
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
