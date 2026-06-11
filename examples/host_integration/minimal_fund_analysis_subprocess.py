"""Minimal host integration: call FundAnalysisSkill via subprocess.

Demonstrates a host process calling the runtime bridge CLI with
subprocess, using a local JSON fixture. No network, no provider SDK,
no broker execution.

Usage:
    python examples/host_integration/minimal_fund_analysis_subprocess.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "run_skill.py"
FIXTURE = PROJECT_ROOT / "examples" / "runtime_bridge_fund_analysis_input.json"


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
        "--skill", "fund_analysis",
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
    result = {
        "ok": data.get("ok") is True,
        "status": data.get("status"),
        "has_portfolio_summary": "portfolio_summary" in artifacts,
        "has_report_sections": "report_sections" in artifacts,
        "has_analysis_plan": "analysis_plan" in artifacts,
        "has_formal_decision": any(
            k in artifacts for k in ("decision", "decisions", "execution_ledger")
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result["ok"], "run_skill.py returned ok=false"
    assert result["has_portfolio_summary"], "Missing portfolio_summary"
    assert result["has_report_sections"], "Missing report_sections"
    assert result["has_analysis_plan"], "Missing analysis_plan"
    assert not result["has_formal_decision"], (
        "fund_analysis must not emit formal Decision/ExecutionLedger"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
