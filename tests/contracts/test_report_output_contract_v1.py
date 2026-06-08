"""Contract tests for report output v1 — report_sections, report_outline, report_quality_gate."""

from __future__ import annotations

import json

import pytest

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.portfolio.report_composer import (
    SECTION_ORDER,
    compose_personal_fund_report,
    render_report_markdown,
)

EXPECTED_SECTION_IDS = [sid for sid, _ in SECTION_ORDER]
EXPECTED_SECTION_KEYS = {"id", "title", "status", "bullets", "data_sources", "limitations"}
VALID_STATUSES = {"OK", "PARTIAL", "MISSING"}


def _full_payload():
    return {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 500000,
            "cash_available": 50000,
            "positions": [
                {"fund_code": "110011", "fund_name": "Equity Fund", "current_value": 300000, "total_cost": 280000, "shares": 200000, "target_weight": 0.6, "tags": ["equity"]},
                {"fund_code": "220022", "fund_name": "Bond Fund", "current_value": 150000, "total_cost": 145000, "shares": 120000, "target_weight": 0.3, "tags": ["bond"]},
            ],
        },
        "fund_profiles": {
            "110011": {"fund_code": "110011", "name": "Equity Fund", "fund_type": "equity"},
            "220022": {"fund_code": "220022", "name": "Bond Fund", "fund_type": "bond"},
        },
        "nav_history": {
            "110011": [{"date": "2025-06-01", "nav": 1.30}, {"date": "2026-06-01", "nav": 1.50}],
            "220022": [{"date": "2025-06-01", "nav": 1.15}, {"date": "2026-06-01", "nav": 1.20}],
        },
        "holdings": {
            "110011": [{"name": "Stock A", "weight": 0.08, "industry": "tech"}],
            "220022": [{"name": "Bond B", "weight": 0.05, "industry": "govt"}],
        },
        "risk_profile": {"risk_level": "moderate", "max_single_fund_weight": 0.6},
        "constraints": {"min_trade_amount": 1000},
    }


class TestReportSectionsContract:
    def test_report_sections_has_expected_ids_in_order(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t1", step_id="s1", skill_name="fund_analysis", payload=_full_payload(),
        ))
        report_sections = output.artifacts.get("report_sections", [])
        actual_ids = [s["id"] for s in report_sections]
        assert actual_ids == EXPECTED_SECTION_IDS, f"expected {EXPECTED_SECTION_IDS}, got {actual_ids}"

    def test_every_section_has_required_keys(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t2", step_id="s2", skill_name="fund_analysis", payload=_full_payload(),
        ))
        report_sections = output.artifacts.get("report_sections", [])
        for section in report_sections:
            missing = EXPECTED_SECTION_KEYS - set(section.keys())
            assert not missing, f"section {section['id']} missing keys: {missing}"

    def test_every_status_is_valid(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t3", step_id="s3", skill_name="fund_analysis", payload=_full_payload(),
        ))
        report_sections = output.artifacts.get("report_sections", [])
        for section in report_sections:
            assert section["status"] in VALID_STATUSES, f"section {section['id']} status={section['status']}"

    def test_bullets_are_strings(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t4", step_id="s4", skill_name="fund_analysis", payload=_full_payload(),
        ))
        report_sections = output.artifacts.get("report_sections", [])
        for section in report_sections:
            for b in section["bullets"]:
                assert isinstance(b, str), f"section {section['id']} has non-string bullet: {b}"

    def test_report_outline_mirrors_section_ids_and_order(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t5", step_id="s5", skill_name="fund_analysis", payload=_full_payload(),
        ))
        outline = output.artifacts.get("report_outline", [])
        outline_ids = [o["id"] for o in outline]
        assert outline_ids == EXPECTED_SECTION_IDS

    def test_outline_items_have_id_title_status(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t6", step_id="s6", skill_name="fund_analysis", payload=_full_payload(),
        ))
        outline = output.artifacts.get("report_outline", [])
        for item in outline:
            assert "id" in item
            assert "title" in item
            assert "status" in item

    def test_report_quality_gate_has_required_keys(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t7", step_id="s7", skill_name="fund_analysis", payload=_full_payload(),
        ))
        gate = output.artifacts.get("report_quality_gate", {})
        assert "grade" in gate
        assert "can_publish_professional_report" in gate
        assert "reason" in gate

    def test_full_payload_produces_grade_b_or_a(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t8", step_id="s8", skill_name="fund_analysis", payload=_full_payload(),
        ))
        gate = output.artifacts.get("report_quality_gate", {})
        assert gate["grade"] in ("A", "B")


class TestRenderMarkdownContract:
    def test_markdown_includes_all_section_titles(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t9", step_id="s9", skill_name="fund_analysis", payload=_full_payload(),
        ))
        sections = output.artifacts.get("report_sections", [])
        md = render_report_markdown(sections)
        for _, title in SECTION_ORDER:
            assert title in md, f"missing title '{title}' in markdown"

    def test_markdown_does_not_contain_decision(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t10", step_id="s10", skill_name="fund_analysis", payload=_full_payload(),
        ))
        sections = output.artifacts.get("report_sections", [])
        md = render_report_markdown(sections)
        assert "Decision" not in md
        assert "ExecutionLedger" not in md

    def test_markdown_is_deterministic(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t11", step_id="s11", skill_name="fund_analysis", payload=_full_payload(),
        ))
        sections = output.artifacts.get("report_sections", [])
        md1 = render_report_markdown(sections)
        md2 = render_report_markdown(sections)
        assert md1 == md2


class TestDecisionBoundary:
    def test_fund_analysis_output_excludes_decision(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t12", step_id="s12", skill_name="fund_analysis", payload=_full_payload(),
        ))
        assert "decision" not in output.artifacts
        assert "execution_ledger" not in output.artifacts

    def test_fund_analysis_output_includes_report_sections(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t13", step_id="s13", skill_name="fund_analysis", payload=_full_payload(),
        ))
        assert "report_sections" in output.artifacts
        assert "report_outline" in output.artifacts
        assert "report_quality_gate" in output.artifacts

    def test_fund_analysis_evidence_items_are_not_decisions(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t14", step_id="s14", skill_name="fund_analysis", payload=_full_payload(),
        ))
        for item in output.evidence_items:
            ev_type = getattr(item, "evidence_type", "")
            assert "decision" not in str(ev_type).lower()


class TestJsonSerialization:
    def test_report_sections_serializable(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t15", step_id="s15", skill_name="fund_analysis", payload=_full_payload(),
        ))
        sections = output.artifacts.get("report_sections", [])
        dumped = json.dumps(sections)
        loaded = json.loads(dumped)
        assert loaded == sections

    def test_report_quality_gate_serializable(self):
        skill = FundAnalysisSkill()
        output = skill.run(SkillInput(
            task_id="t16", step_id="s16", skill_name="fund_analysis", payload=_full_payload(),
        ))
        gate = output.artifacts.get("report_quality_gate", {})
        dumped = json.dumps(gate)
        loaded = json.loads(dumped)
        assert loaded == gate


class TestContractDocument:
    def test_contract_doc_exists(self):
        from pathlib import Path
        doc = Path("docs/contracts/report-output-contract.v1.md")
        assert doc.exists()

    def test_contract_doc_mentions_section_ids(self):
        from pathlib import Path
        content = Path("docs/contracts/report-output-contract.v1.md").read_text(encoding="utf-8")
        for sid in EXPECTED_SECTION_IDS:
            assert sid in content, f"contract doc missing section id: {sid}"

    def test_contract_doc_defines_status_enum(self):
        from pathlib import Path
        content = Path("docs/contracts/report-output-contract.v1.md").read_text(encoding="utf-8")
        assert "OK" in content
        assert "PARTIAL" in content
        assert "MISSING" in content
