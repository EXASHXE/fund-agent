"""Generic host smoke integration tests.

Tests the external-host flow: discover skills, map slugs, inspect
contracts, validate fixtures, run deterministic smoke cases, and
verify boundary rules.

Uses in-process bridge for semantic tests and subprocess only for
CLI boundary smoke. Marked with @pytest.mark.smoke and
@pytest.mark.subprocess where subprocess is used.
"""

from __future__ import annotations

import json

import pytest

from tests.support.bridge_runner import (
    parse_stdout_json,
    project_root,
    run_bridge_inprocess_json,
    run_bridge_inprocess_metadata,
    run_bridge_subprocess,
)
from tests.support.error_shape import assert_envelope_errors_are_canonical
from tests.support.formal_boundary import FORMAL_DECISION_ARTIFACT_KEYS
from tests.support.host_smoke_cases import HOST_SMOKE_CASES

ROOT = project_root()

ALL_SKILLS = ["fund_analysis", "decision_support", "news_research", "sentiment_analysis", "thesis_generation"]
ALL_SLUGS = ["fund-analysis", "decision-support", "news-research", "sentiment-analysis", "thesis-generation"]


class TestListSkills:
    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_list_skills_returns_ok(self):
        result = run_bridge_subprocess(["--list-skills", "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is True

    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_list_skills_includes_all_runtime_ids(self):
        result = run_bridge_subprocess(["--list-skills", "--pretty"])
        data = parse_stdout_json(result)
        runtime_ids = {item["runtime_id"] for item in data["skills"]}
        assert set(ALL_SKILLS) <= runtime_ids

    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_list_skills_has_doc_slug_hyphenated(self):
        result = run_bridge_subprocess(["--list-skills", "--pretty"])
        data = parse_stdout_json(result)
        for item in data["skills"]:
            slug = item.get("doc_slug", "")
            assert "_" not in slug, f"doc_slug must be hyphenated: {slug}"
            assert "-" in slug, f"doc_slug must use hyphens: {slug}"

    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_list_skills_each_has_runtime_id_and_doc_slug(self):
        result = run_bridge_subprocess(["--list-skills", "--pretty"])
        data = parse_stdout_json(result)
        for item in data["skills"]:
            assert "runtime_id" in item
            assert "doc_slug" in item


class TestExplainInput:
    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_explain_input_by_runtime_id(self, skill):
        data = run_bridge_inprocess_metadata(skill=skill, explain_input=True, pretty=True)
        assert data.get("ok") is True
        assert data.get("skill_name") == skill

    @pytest.mark.parametrize("slug", ALL_SLUGS)
    def test_explain_input_by_doc_slug(self, slug):
        data = run_bridge_inprocess_metadata(skill=slug, explain_input=True, pretty=True)
        assert data.get("ok") is True


class TestOutputSchema:
    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_output_schema_by_runtime_id(self, skill):
        data = run_bridge_inprocess_metadata(skill=skill, output_schema=True, pretty=True)
        assert data.get("ok") is True
        assert data.get("skill_name") == skill

    @pytest.mark.parametrize("slug", ALL_SLUGS)
    def test_output_schema_by_doc_slug(self, slug):
        data = run_bridge_inprocess_metadata(skill=slug, output_schema=True, pretty=True)
        assert data.get("ok") is True


class TestValidateFixtures:
    @pytest.mark.parametrize("case", [c for c in HOST_SMOKE_CASES if c.input_path], ids=lambda c: c.skill)
    def test_validate_fixture_succeeds(self, case):
        input_text = (ROOT / case.input_path).read_text(encoding="utf-8")
        data = run_bridge_inprocess_metadata(
            skill=case.skill,
            validate_input=True,
            input_text=input_text,
            pretty=True,
        )
        assert data.get("ok") is True
        vr = data.get("validation_result", {})
        assert vr.get("valid") is True or vr.get("severity") in {"OK", "PARTIAL", "WARN"}


class TestRunSmokeCases:
    @pytest.mark.parametrize("case", [c for c in HOST_SMOKE_CASES if c.input_path and not c.emit_report], ids=lambda c: f"{c.skill}_json")
    def test_json_smoke_case(self, case):
        fixture = json.loads((ROOT / case.input_path).read_text(encoding="utf-8"))
        result = run_bridge_inprocess_json(
            skill=case.skill,
            input_data=fixture,
        )
        assert result.get("skill_name") == case.skill
        assert result.get("status") in case.expected_statuses
        artifacts = result.get("artifacts", {})
        for key in case.expected_artifacts:
            assert key in artifacts, f"missing expected artifact: {key}"
        for key in case.forbidden_artifacts:
            assert key not in artifacts, f"forbidden artifact present: {key}"
        errors = result.get("errors", [])
        if errors:
            assert_envelope_errors_are_canonical(result)

    @pytest.mark.parametrize("case", [c for c in HOST_SMOKE_CASES if c.mcp_responses], ids=lambda c: c.skill)
    def test_mcp_smoke_case(self, case):
        input_data = {
            "payload": {"query": "fund:FAKE001"},
            "mcp_responses": case.mcp_responses,
        }
        result = run_bridge_inprocess_json(
            skill=case.skill,
            input_data=input_data,
        )
        assert result.get("skill_name") == case.skill
        assert result.get("status") in case.expected_statuses
        artifacts = result.get("artifacts", {})
        for key in case.expected_artifacts:
            assert key in artifacts, f"missing expected artifact: {key}"
        for key in case.forbidden_artifacts:
            assert key not in artifacts, f"forbidden artifact present: {key}"


class TestHyphenSlugSmoke:
    @pytest.mark.parametrize("slug", ALL_SLUGS)
    def test_hyphenated_slug_resolves(self, slug):
        data = run_bridge_inprocess_metadata(skill=slug, explain_input=True, pretty=True)
        assert data.get("ok") is True

    def test_fund_analysis_hyphenated_runs(self):
        result = run_bridge_inprocess_json(
            skill="fund-analysis",
            input_data=json.loads((ROOT / "examples/scenarios/cn_fund_7d_redemption_fee.json").read_text(encoding="utf-8")),
        )
        assert result.get("skill_name") == "fund_analysis"
        assert result.get("status") in {"OK", "PARTIAL"}

    def test_decision_support_hyphenated_runs(self):
        result = run_bridge_inprocess_json(
            skill="decision-support",
            input_data=json.loads((ROOT / "examples/decision_support/single_active_buy_with_evidence.json").read_text(encoding="utf-8")),
        )
        assert result.get("skill_name") == "decision_support"

    def test_thesis_generation_hyphenated_runs(self):
        result = run_bridge_inprocess_json(
            skill="thesis-generation",
            input_data=json.loads((ROOT / "examples/thesis_generation/evidence_graph_balanced_thesis.json").read_text(encoding="utf-8")),
        )
        assert result.get("skill_name") == "thesis_generation"


class TestMarkdownEmit:
    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_fund_analysis_markdown_is_not_json(self, tmp_path):
        report_path = tmp_path / "report.md"
        result = run_bridge_subprocess([
            "--skill", "fund_analysis",
            "--input", "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "--emit-report", "markdown",
            "--output", str(report_path),
        ])
        assert result.returncode == 0, result.stderr
        text = report_path.read_text(encoding="utf-8")
        assert text.startswith("# Personal fund report")
        assert "## Executive summary" in text
        assert "## Limitations" in text
        with pytest.raises(json.JSONDecodeError):
            json.loads(text)

    @pytest.mark.subprocess
    @pytest.mark.smoke
    def test_fund_analysis_markdown_no_formal_decision(self, tmp_path):
        report_path = tmp_path / "report.md"
        result = run_bridge_subprocess([
            "--skill", "fund_analysis",
            "--input", "examples/scenarios/cn_fund_7d_redemption_fee.json",
            "--emit-report", "markdown",
            "--output", str(report_path),
        ])
        assert result.returncode == 0, result.stderr
        text = report_path.read_text(encoding="utf-8")
        for key in FORMAL_DECISION_ARTIFACT_KEYS:
            assert f"## {key.replace('_', ' ').title()}" not in text, (
                f"Markdown report must not contain formal decision section: {key}"
            )
