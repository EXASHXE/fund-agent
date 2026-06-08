#!/usr/bin/env python3
"""Regenerate decision_support golden regression snapshots.

This script is local test tooling only. It runs selected fake/sample fixtures
through the existing runtime bridge CLI and writes normalized JSON snapshots.
It does not fetch data, call providers, import provider SDKs, invoke the
OpenCode plugin, or modify runtime code.
"""

from __future__ import annotations

import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.golden.decision_support_golden import (  # noqa: E402
    DECISION_SUPPORT_GOLDEN_FIXTURES,
    JSON_SNAPSHOT_DIR,
    normalize_bridge_json,
    run_decision_support_json,
    serialize_snapshot,
)


def main() -> int:
    JSON_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for fixture in DECISION_SUPPORT_GOLDEN_FIXTURES:
        output = run_decision_support_json(fixture)
        normalized = normalize_bridge_json(output)
        fixture.json_snapshot_path.write_text(
            serialize_snapshot(normalized),
            encoding="utf-8",
        )
        print(f"wrote {fixture.json_snapshot_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
