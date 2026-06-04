"""Verify docs reflect the end-to-end personal fund report flow."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _check_doc(path: str, *terms: str):
    content = Path(PROJECT_ROOT, path).read_text(encoding="utf-8")
    for term in terms:
        assert term in content, f"{path} missing: {term}"


class TestPersonalReportDocs:
    def test_workflow_doc_mentions_report_only_flow(self):
        _check_doc(
            "docs/workflows/personal-fund-report.md",
            "report_sections",
            "report_quality_gate",
            "FundAnalysisSkill",
        )

    def test_workflow_doc_mentions_decision_handoff(self):
        _check_doc(
            "docs/workflows/personal-fund-report.md",
            "decision_support",
            "DecisionSupportSkill",
        )

    def test_skill_io_docs_mention_report_sections(self):
        _check_doc(
            "docs/skill-io-examples.md",
            "report_sections",
            "report_outline",
            "report_quality_gate",
        )

    def test_docs_do_not_claim_opencode_plugin_runs_python(self):
        content = Path(PROJECT_ROOT, "docs/host-compatibility.md").read_text()
        assert "not run the Python runtime" in content.replace("*", "")

    def test_docs_do_not_claim_fund_agent_fetches_data(self):
        for path in ["docs/host-integration.md", "docs/plugin-api.md"]:
            content = Path(PROJECT_ROOT, path).read_text(encoding="utf-8")
            # Should say host owns data, not fund-agent
            assert "host-owned" in content or "host" in content.lower()

    def test_docs_do_not_treat_rebalance_plan_as_executable(self):
        content = Path(PROJECT_ROOT, "docs/workflows/personal-fund-report.md").read_text()
        assert "suggested" in content.lower() and "rebalance" in content.lower()
        # Should assert it's a suggestion, not a formal instruction
        assert "not a decision" in content.lower() or "not executable" in content.lower() or \
               "suggested" in content.lower()
