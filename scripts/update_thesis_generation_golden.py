#!/usr/bin/env python3
"""Regenerate thesis_generation golden regression snapshots."""

from __future__ import annotations

import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.golden.thesis_generation_golden import (
    THESIS_GENERATION_GOLDEN_FIXTURES,
    JSON_SNAPSHOT_DIR,
    normalize_bridge_json,
    run_thesis_generation_json,
    serialize_snapshot,
)


def main() -> int:
    JSON_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for fixture in THESIS_GENERATION_GOLDEN_FIXTURES:
        output = run_thesis_generation_json(fixture)
        normalized = normalize_bridge_json(output)
        fixture.json_snapshot_path.write_text(
            serialize_snapshot(normalized),
            encoding="utf-8",
        )
        print(f"wrote {fixture.json_snapshot_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
