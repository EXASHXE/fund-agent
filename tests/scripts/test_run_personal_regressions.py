"""Tests for the personal portfolio regression runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_personal_regressions.py"


def test_personal_regression_runner_json_outputs_summary():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["summary"]["scenario_count"] >= 12
    assert payload["summary"]["failed_count"] == 0
    assert payload["summary"]["no_broker_execution"] is True
    assert payload["results"]


def test_personal_regression_runner_can_filter_one_scenario():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--scenario",
            "short_holding_7day_fee_sell_zh",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["summary"]["scenario_count"] == 1
    [scenario] = payload["results"]
    assert scenario["scenario_id"] == "short_holding_7day_fee_sell_zh"
    assert scenario["decision_status"] in {"BLOCKED", "DOWNGRADED"}
    assert scenario["no_broker_execution"] is True
