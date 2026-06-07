#!/usr/bin/env python3
"""Regenerate fund_analysis golden regression snapshots.

This script is local test tooling only. It runs selected fake/sample fixtures
through the existing runtime bridge CLI and writes normalized JSON and Markdown
snapshots. It does not fetch data, call providers, import provider SDKs, invoke
the OpenCode plugin, or modify runtime code.
"""

from __future__ import annotations

import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.golden.fund_analysis_golden import (  # noqa: E402
    FUND_ANALYSIS_GOLDEN_FIXTURES,
    JSON_SNAPSHOT_DIR,
    MARKDOWN_SNAPSHOT_DIR,
    normalize_bridge_json,
    run_fund_analysis_json,
    run_fund_analysis_markdown,
    serialize_snapshot,
)


def main() -> int:
    JSON_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for fixture in FUND_ANALYSIS_GOLDEN_FIXTURES:
        output = run_fund_analysis_json(fixture)
        normalized = normalize_bridge_json(output)
        fixture.json_snapshot_path.write_text(
            serialize_snapshot(normalized),
            encoding="utf-8",
        )
        print(f"wrote {fixture.json_snapshot_path.relative_to(ROOT)}")

        if fixture.markdown_snapshot:
            markdown = run_fund_analysis_markdown(fixture)
            fixture.markdown_snapshot_path.write_text(markdown, encoding="utf-8")
            print(f"wrote {fixture.markdown_snapshot_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
