#!/usr/bin/env python3
"""Check skillpack examples for consistency with manifest and contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXAMPLES_DIR = Path("skillpack/examples")


def main() -> int:
    errors = []
    ok = 0

    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue

        name = path.name

        # Output examples may not have task_id/step_id
        if "_output." in name:
            _check_output(name, data, errors)
        elif "_input." in name or "host_minimal" in name:
            _check_input(name, data, errors)

        # All examples must be free of ResearchOS and legacy refs
        raw = path.read_text(encoding="utf-8")
        if "src.core.research_os" in raw:
            errors.append(f"{name}: references ResearchOS")
        if "legacy" in raw.lower():
            errors.append(f"{name}: references legacy")

        ok += 1

    print(f"Examples checked: {ok}")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("All examples OK")
    return 0


def _check_input(name: str, data: dict, errors: list[str]) -> None:
    for field in ("task_id", "step_id", "skill_name", "payload"):
        if field not in data:
            pass  # host_minimal has different structure
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


if __name__ == "__main__":
    sys.exit(main())
