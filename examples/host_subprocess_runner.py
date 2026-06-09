"""Minimal subprocess host reference runner.

This is a reference external host pattern. It demonstrates how an
external host can call the fund-agent runtime bridge as a subprocess.

- Host owns data fetching and provider integration.
- This example uses fake/sample fixtures only.
- No broker/order execution.
- No network calls.
- No provider SDKs.
- Does not import src.skills_runtime or runtime skill classes directly.
- Uses only Python standard library.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_run_cmd(repo_root: Path) -> list[str]:
    return [sys.executable, str(repo_root / "scripts" / "run_skill.py")]


def run_json_skill(
    skill: str,
    input_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run a runtime bridge skill via subprocess and return the JSON envelope.

    Uses ``python scripts/run_skill.py`` by default. The command can be
    overridden via the ``FUND_AGENT_RUN_CMD`` environment variable (JSON
    array of strings).
    """
    root = repo_root or _default_repo_root()
    cmd = _default_run_cmd(root)
    env_cmd = _env_run_cmd()
    if env_cmd is not None:
        cmd = env_cmd
    full_cmd = cmd + [
        "--skill", skill,
        "--input", str(input_path),
    ]
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        timeout=120,
        cwd=str(root),
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")
        raise RuntimeError(
            f"Runtime bridge failed (rc={result.returncode}): {stderr[:500]}"
        )
    return json.loads(stdout)


def run_markdown_report(
    input_path: Path,
    *,
    repo_root: Path | None = None,
) -> str:
    """Run fund_analysis and return the Markdown report string.

    Uses ``--emit-report markdown`` which writes Markdown on success.
    """
    root = repo_root or _default_repo_root()
    cmd = _default_run_cmd(root)
    env_cmd = _env_run_cmd()
    if env_cmd is not None:
        cmd = env_cmd
    full_cmd = cmd + [
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--emit-report", "markdown",
    ]
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        timeout=120,
        cwd=str(root),
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")
        raise RuntimeError(
            f"Runtime bridge failed (rc={result.returncode}): {stderr[:500]}"
        )
    return stdout


def _env_run_cmd() -> list[str] | None:
    import os
    val = os.environ.get("FUND_AGENT_RUN_CMD")
    if val:
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val.split()
    return None


def main() -> None:
    root = _default_repo_root()

    print("=== fund_analysis (JSON) ===")
    fa_result = run_json_skill(
        "fund_analysis",
        root / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json",
        repo_root=root,
    )
    print(f"  ok={fa_result.get('ok')}  status={fa_result.get('status')}  skill={fa_result.get('skill_name')}")

    print()
    print("=== fund_analysis (Markdown report) ===")
    md = run_markdown_report(
        root / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json",
        repo_root=root,
    )
    lines = md.strip().split("\n")
    for line in lines[:5]:
        print(f"  {line}")
    if len(lines) > 5:
        print(f"  ... ({len(lines)} total lines)")

    print()
    print("=== decision_support (JSON) ===")
    ds_result = run_json_skill(
        "decision_support",
        root / "examples" / "decision_support" / "single_active_buy_with_evidence.json",
        repo_root=root,
    )
    print(f"  ok={ds_result.get('ok')}  status={ds_result.get('status')}  skill={ds_result.get('skill_name')}")

    print()
    print("=== thesis_generation (JSON) ===")
    tg_result = run_json_skill(
        "thesis_generation",
        root / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json",
        repo_root=root,
    )
    print(f"  ok={tg_result.get('ok')}  status={tg_result.get('status')}  skill={tg_result.get('skill_name')}")


if __name__ == "__main__":
    main()
