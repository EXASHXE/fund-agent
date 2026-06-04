"""Minimal end-to-end personal fund report flow.

Reference workflow for the user request: "分析下我的基金给出报告"

This example demonstrates the canonical report-only flow:
1. Host provides structured fund/portfolio data (the payload).
2. FundAnalysisSkill produces report_sections, report_outline,
   report_quality_gate, data_completeness, analysis_coverage, and
   report_limitations.
3. render_report_markdown() renders a deterministic Markdown report.
4. The flow stops here — no formal decisions are produced.

Usage:
    python examples/minimal_personal_fund_report_flow.py
    python examples/minimal_personal_fund_report_flow.py --input my_data.json
    python examples/minimal_personal_fund_report_flow.py --output /tmp/report.md

Safety:
- No network calls, no provider SDKs, no OpenCode plugin.
- Does not produce Decision or ExecutionLedger.
- report_sections are deterministic; suggested_rebalance_plan is analysis
  only, not executable trade instructions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.portfolio.report_composer import render_report_markdown

DEFAULT_INPUT = PROJECT_ROOT / "examples" / "runtime_bridge_personal_report_quality_input.json"


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_report_flow(input_path: str, output_path: str | None) -> int:
    data = load_payload(input_path)

    skill_input = SkillInput(
        task_id="personal-fund-report-flow",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=data.get("payload", data),
    )

    output = FundAnalysisSkill().run(skill_input)

    artifacts = output.artifacts
    report_sections = artifacts.get("report_sections", [])
    report_outline = artifacts.get("report_outline", [])
    quality_gate = artifacts.get("report_quality_gate", {})
    data_completeness = artifacts.get("data_completeness", {})
    analysis_coverage = artifacts.get("analysis_coverage", {})
    report_limitations = artifacts.get("report_limitations", [])
    warnings = output.warnings

    md = render_report_markdown(report_sections)

    result = {
        "status": output.status,
        "data_completeness": data_completeness,
        "analysis_coverage": analysis_coverage,
        "report_quality_gate": quality_gate,
        "report_outline": report_outline,
        "report_limitations": report_limitations,
        "warnings": warnings,
        "markdown_report": md,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(md)
        result.pop("markdown_report", None)
        json.dump({"ok": True, "output_file": output_path, **result}, sys.stdout, indent=2, ensure_ascii=False)
    else:
        json.dump({"ok": True, **result}, sys.stdout, indent=2, ensure_ascii=False)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end personal fund report flow")
    parser.add_argument(
        "--input", type=str, default=str(DEFAULT_INPUT),
        help="Path to JSON input payload (default: examples/runtime_bridge_personal_report_quality_input.json)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional path to write Markdown report file",
    )
    args = parser.parse_args()
    return run_report_flow(args.input, args.output)


if __name__ == "__main__":
    sys.exit(main())
