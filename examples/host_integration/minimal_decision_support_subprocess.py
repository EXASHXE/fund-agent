"""Minimal host integration: call DecisionSupportSkill via subprocess.

Demonstrates a host process calling the runtime bridge CLI with
subprocess, using the v1.2 decision_support sample input. The scenario
demonstrates safe gating: an active SELL is requested with valid
evidence anchors, and the output includes execution_ledger with
ledger_summary, evidence_anchor_diagnostics, and
risk_constraint_conflicts.

No broker execution. No provider SDK. No network.

Usage:
    python examples/host_integration/minimal_decision_support_subprocess.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "run_skill.py"
FIXTURE = PROJECT_ROOT / "examples" / "runtime_bridge_decision_support_input_v2.json"


def main() -> int:
    if not SCRIPT.is_file():
        print(f"Error: run_skill.py not found at {SCRIPT}", file=sys.stderr)
        return 1

    if not FIXTURE.is_file():
        print(f"Error: fixture not found at {FIXTURE}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--skill", "decision_support",
        "--input", str(FIXTURE),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else (proc.stderr or "")
        print(f"Error: run_skill.py returned {proc.returncode}", file=sys.stderr)
        print(stderr, file=sys.stderr)
        return 1

    stdout = proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"Error: output is not valid JSON", file=sys.stderr)
        print(stdout[:500], file=sys.stderr)
        return 1

    artifacts = data.get("artifacts", {})
    execution_ledger = artifacts.get("execution_ledger", {})

    result = {
        "ok": data.get("ok") is True,
        "status": data.get("status"),
        "has_decision": "decision" in artifacts,
        "has_execution_ledger": bool(execution_ledger),
        "has_ledger_summary": isinstance(execution_ledger.get("ledger_summary"), dict),
        "has_evidence_anchor_diagnostics": "evidence_anchor_diagnostics" in artifacts,
        "has_risk_constraint_conflicts": "risk_constraint_conflicts" in artifacts,
        "has_broker_fields": any(
            k in artifacts for k in ("broker_order", "order_execution", "trade_execution")
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result["has_decision"], "Missing decision artifact"
    assert result["has_execution_ledger"], "Missing execution_ledger"
    assert result["has_ledger_summary"], "Missing ledger_summary in execution_ledger"
    assert result["has_evidence_anchor_diagnostics"], "Missing evidence_anchor_diagnostics"
    assert result["has_risk_constraint_conflicts"], "Missing risk_constraint_conflicts"
    assert not result["has_broker_fields"], "Must not contain broker/order execution fields"
    return 0


if __name__ == "__main__":
    sys.exit(main())
