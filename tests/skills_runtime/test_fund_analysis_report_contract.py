"""Unit tests for fund_analysis report contract — report_sections shape validation."""

from src.tools.portfolio.report_sections.render import compose_personal_fund_report


class TestReportContract:
    def test_compose_returns_required_keys(self):
        result = compose_personal_fund_report({}, warnings=[])
        assert "report_sections" in result
        assert "report_outline" in result
        assert "quality_gate" in result

    def test_report_sections_is_list(self):
        result = compose_personal_fund_report({}, warnings=[])
        assert isinstance(result["report_sections"], list)

    def test_quality_gate_has_grade(self):
        result = compose_personal_fund_report({}, warnings=[])
        qg = result["quality_gate"]
        assert "grade" in qg

    def test_each_section_has_required_keys(self):
        result = compose_personal_fund_report({}, warnings=[])
        for section in result["report_sections"]:
            assert "id" in section, f"Section missing 'id': {section}"
            assert "title" in section, f"Section missing 'title': {section}"
            assert "status" in section, f"Section missing 'status': {section}"

    def test_report_outline_matches_sections(self):
        result = compose_personal_fund_report({}, warnings=[])
        sections = result["report_sections"]
        outline = result["report_outline"]
        assert len(outline) == len(sections)

    def test_quality_gate_has_can_publish(self):
        result = compose_personal_fund_report({}, warnings=[])
        qg = result["quality_gate"]
        assert "can_publish_professional_report" in qg
        assert isinstance(qg["can_publish_professional_report"], bool)

    def test_quality_gate_has_reason(self):
        result = compose_personal_fund_report({}, warnings=[])
        qg = result["quality_gate"]
        assert "reason" in qg
        assert isinstance(qg["reason"], str)

    def test_warnings_in_result(self):
        result = compose_personal_fund_report({}, warnings=["test warning"])
        assert "test warning" in result["warnings"]
