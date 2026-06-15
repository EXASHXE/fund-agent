"""Tests that report-template.md sections stay in sync with SECTION_ORDER."""

import os
import re

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TEMPLATE_PATH = os.path.join(
    _REPO_ROOT, "skills", "fund-analysis", "references", "report-template.md"
)

# Import SECTION_ORDER from the runtime
from src.tools.portfolio.report_composer import SECTION_ORDER


def _extract_template_sections():
    """Extract numbered section IDs from the Canonical sections list."""
    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # Match lines like "1. `section_id`" or "27. `section_id`"
    return re.findall(r"^\d+\.\s+`([^`]+)`", content, re.MULTILINE)


class TestReportTemplateSync:
    def test_template_sections_match_section_order(self):
        template_ids = _extract_template_sections()
        runtime_ids = [section_id for section_id, _ in SECTION_ORDER]
        assert template_ids == runtime_ids, (
            f"Report template sections do not match SECTION_ORDER.\n"
            f"In template but not runtime: {set(template_ids) - set(runtime_ids)}\n"
            f"In runtime but not template: {set(runtime_ids) - set(template_ids)}\n"
            f"Template order: {template_ids}\n"
            f"Runtime order: {runtime_ids}"
        )

    def test_template_has_all_section_ids(self):
        template_ids = set(_extract_template_sections())
        runtime_ids = {section_id for section_id, _ in SECTION_ORDER}
        assert template_ids == runtime_ids
