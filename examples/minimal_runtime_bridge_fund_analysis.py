"""Minimal host demo: call the runtime bridge CLI from Python.

This shows the simplest way to invoke ``fund-agent`` runtime skills
from a host that does not want to import the internal Python
modules directly. The host spawns ``python scripts/run_skill.py``
as a subprocess, reads the JSON envelope from stdout, and parses
it. The bridge does not fetch data, does not import provider
SDKs, and does not run an agent loop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def run_skill(
    skill_name: str,
    input_payload: dict,
    *,
    manifest_path: str | None = None,
) -> dict:
    """Spawn the bridge CLI and return the parsed JSON envelope.

    Diagnostics (stderr) are passed through unchanged. The bridge
    returns exit code 0 on success, nonzero on bridge-level
    failure.
    """
    args = [PYTHON, str(SCRIPT), "--skill", skill_name, "--input", "-"]
    if manifest_path:
        args.extend(["--manifest", manifest_path])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        input=json.dumps(input_payload),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        # Bridge-level failure. Print stderr and re-raise so the
        # caller sees both the exit code and any diagnostics.
        print(proc.stderr, file=sys.stderr, end="")
        raise RuntimeError(
            f"runtime bridge failed: rc={proc.returncode}, "
            f"stdout={proc.stdout!r}, stderr={proc.stderr!r}"
        )
    return json.loads(proc.stdout)


def main() -> None:
    payload = {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 100000,
                "cash_available": 10000,
                "positions": [],
            },
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
        }
    }
    result = run_skill("fund_analysis", payload)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
