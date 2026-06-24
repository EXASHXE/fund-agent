"""Pure workflow report tools -- rendering, quality gate, status, safety.

This package must NOT import from ``src.skills_runtime`` -- it is a pure
tools layer. Skill orchestration, evidence bridge, and intent helpers live
in ``src.skills_runtime.workflow`` and are surfaced via the
``src.fund_agent.workflow`` public facade.

Public API surface (import from submodules directly):

- ``src.tools.workflow.final_report.compose_advisory_workflow_report``
- ``src.tools.workflow.advisory_quality_gate.evaluate_advisory_quality_gate``
- ``src.tools.workflow.report_status.compute_report_status`` (and siblings)
- ``src.tools.workflow.report_safety.build_safety_boundary`` (and FORBIDDEN_EXECUTION_FIELDS)
- ``src.tools.workflow.report_zh.build_chinese_summary`` / ``localize_section_titles``
- ``src.tools.workflow.report_helpers.theme_text`` / ``dedupe_preserve_order``
"""

from __future__ import annotations

__all__: list[str] = []
