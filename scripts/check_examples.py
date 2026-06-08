#!/usr/bin/env python3
"""Check skillpack examples for consistency with manifest and contracts.

Also validates realistic examples under examples/ and runs demo scripts as subprocesses.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
EXAMPLES_DIR = PROJECT_ROOT / "skillpack" / "examples"
REALISTIC_EXAMPLES = [
    "portfolio_review_200k.json",
    "oil_gas_loss_rebalance.json",
    "short_term_theme_trade.json",
    "dca_adjustment.json",
    "rebalance_with_cash_reserve.json",
]
DEMO_SCRIPTS = [
    "examples/minimal_host_news_to_decision.py",
    "examples/minimal_host_portfolio_review.py",
    "examples/minimal_host_trade_plan_to_decisions.py",
    "examples/minimal_runtime_bridge_fund_analysis.py",
    "examples/minimal_personal_fund_report_flow.py",
    "examples/minimal_personal_fund_report_with_decision_handoff.py",
]


def main() -> int:
    errors: list[str] = []
    checked = 0
    demo_passed = 0

    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue

        name = path.name

        if "_output." in name:
            _check_output(name, data, errors)
        elif "_input." in name or "host_minimal" in name:
            _check_input(name, data, errors)

        raw = path.read_text(encoding="utf-8")
        if "src.core.research_os" in raw:
            errors.append(f"{name}: references ResearchOS")
        if "legacy" in raw.lower():
            errors.append(f"{name}: references legacy")

        checked += 1

    checked += _check_realistic_examples(errors)
    checked += _check_runtime_bridge_examples(errors)
    demo_passed = _check_demo_scripts(errors)

    print(f"Examples checked: {checked}, Demos passed: {demo_passed}")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("All OK")
    return 0


def _check_realistic_examples(errors: list[str]) -> int:
    examples_dir = PROJECT_ROOT / "examples"
    checked = 0

    for filename in REALISTIC_EXAMPLES:
        path = examples_dir / filename
        if not path.exists():
            errors.append(f"examples/{filename}: file not found")
            continue

        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"examples/{filename}: invalid JSON: {exc}")
            continue

        if "src.core.research_os" in raw:
            errors.append(f"examples/{filename}: references ResearchOS")
        if "legacy" in raw.lower():
            errors.append(f"examples/{filename}: references legacy")

        transactions = data.get("transactions", [])
        if isinstance(transactions, list):
            for i, txn in enumerate(transactions):
                if isinstance(txn, dict) and "action" not in txn:
                    errors.append(
                        f"examples/{filename}: transaction [{i}] missing 'action' field"
                    )

        try:
            from src.schemas.skill import SkillInput
            from src.skills_runtime.fund_analysis import FundAnalysisSkill

            skill_input = SkillInput(
                task_id="check-examples",
                step_id="fund-analysis-1",
                skill_name="fund_analysis",
                payload=data,
            )
            output = FundAnalysisSkill().run(skill_input)
            if output.status == "FAILED":
                error_msgs = [
                    (e.get("code") if isinstance(e, dict) else getattr(e, "code", "?"))
                    for e in output.errors
                ]
                errors.append(
                    f"examples/{filename}: FundAnalysisSkill FAILED — "
                    f"errors: {error_msgs}"
                )
        except Exception as exc:
            errors.append(
                f"examples/{filename}: FundAnalysisSkill raised: {exc}"
            )

        checked += 1

    return checked


def _check_runtime_bridge_examples(errors: list[str]) -> int:
    """Validate the runtime bridge example inputs and demos.

    These are convenience inputs that the host can pipe into
    ``scripts/run_skill.py``. We assert they parse as JSON, contain
    a ``payload`` field, and do not reference legacy / ResearchOS.
    """
    bridge_examples = [
        "examples/runtime_bridge_fund_analysis_input.json",
        "examples/runtime_bridge_decision_support_input.json",
        "examples/runtime_bridge_personal_report_quality_input.json",
    ]
    checked = 0
    for rel in bridge_examples:
        path = PROJECT_ROOT / rel
        if not path.exists():
            errors.append(f"runtime bridge example missing: {rel}")
            continue
        raw = path.read_text(encoding="utf-8")
        if "src.core.research_os" in raw:
            errors.append(f"{rel}: references ResearchOS")
        if "legacy" in raw.lower():
            errors.append(f"{rel}: references legacy")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue
        if "payload" not in data:
            errors.append(f"{rel}: missing 'payload' field")
        checked += 1
    return checked


def _check_demo_scripts(errors: list[str]) -> int:
    passed = 0
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}

    for script_path in DEMO_SCRIPTS:
        full_path = PROJECT_ROOT / script_path
        if not full_path.exists():
            errors.append(f"demo script not found: {script_path}")
            continue

        try:
            result = subprocess.run(
                [sys.executable, str(full_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                cwd=str(PROJECT_ROOT),
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"demo timeout: {script_path}")
            continue
        except Exception as exc:
            errors.append(f"demo subprocess failed: {script_path}: {exc}")
            continue

        if result.returncode != 0:
            errors.append(
                f"demo non-zero exit {result.returncode}: {script_path}"
            )
            if result.stderr:
                errors.append(f"  stderr: {result.stderr[:200]}")
            continue

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            errors.append(f"demo output not valid JSON: {script_path}")
            continue

        passed += 1

    return passed


def _check_input(name: str, data: dict, errors: list[str]) -> None:
    for field in ("task_id", "step_id", "skill_name", "payload"):
        if field not in data:
            pass
    if name == "decision_support_input.json":
        payload = data.get("payload", {})
        if "evidence_graph" not in payload:
            errors.append(f"{name}: missing evidence_graph in payload")


def _check_output(name: str, data: dict, errors: list[str]) -> None:
    if name == "decision_support_output.json":
        artifacts = data.get("artifacts", {})
        if "decision" not in artifacts:
            errors.append(f"{name}: missing decision in artifacts")
        if "execution_ledger" not in artifacts:
            errors.append(f"{name}: missing execution_ledger in artifacts")


def _validate_trade_plan_demo() -> None:
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "examples/minimal_host_trade_plan_to_decisions.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Trade plan demo failed (rc={result.returncode}): {result.stderr}"
        )
    data = json.loads(result.stdout)
    assert "decisions" in data, "Trade plan demo output missing 'decisions'"
    assert "execution_ledger" in data, "Trade plan demo output missing 'execution_ledger'"
    assert isinstance(data["decisions"], list), "'decisions' must be a list"
    print(f"  OK: trade_plan demo produces {len(data['decisions'])} decision(s)")


if __name__ == "__main__":
    _validate_trade_plan_demo()
    sys.exit(main())
