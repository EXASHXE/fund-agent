"""Tests for deterministic contract-compliant report Markdown rendering."""

from __future__ import annotations

import re

from src.tools.portfolio.report_composer import render_report_markdown


def _sections() -> list[dict]:
    return [
        {
            "id": "executive_summary",
            "title": "Executive summary",
            "status": "OK",
            "bullets": ["Portfolio value is available."],
            "data_sources": ["portfolio_summary"],
            "limitations": [],
        },
        {
            "id": "benchmark_and_peer",
            "title": "Benchmark and peer",
            "status": "PARTIAL",
            "bullets": ["Benchmark data is present."],
            "data_sources": ["benchmark_summary"],
            "limitations": [
                "Peer group data is missing; no peer ranking is fabricated.",
            ],
        },
        {
            "id": "fees_and_redemption",
            "title": "Fees and redemption",
            "status": "MISSING",
            "bullets": [],
            "data_sources": ["fee_summary"],
            "limitations": [
                "Fee schedule is missing; fee analysis is not fabricated.",
            ],
        },
    ]


def test_render_report_markdown_is_deterministic_and_renders_all_headings() -> None:
    sections = _sections()
    first = render_report_markdown(sections)
    second = render_report_markdown(sections)
    assert first == second
    assert first.startswith("# Personal fund report\n")
    for section in sections:
        assert f"## {section['title']}" in first


def test_partial_and_missing_sections_are_annotated() -> None:
    rendered = render_report_markdown(_sections())
    assert "## Benchmark and peer [PARTIAL]" in rendered
    assert "## Fees and redemption [MISSING]" in rendered


def test_global_limitations_footer_includes_affected_section_context() -> None:
    rendered = render_report_markdown(_sections())
    assert "## Limitations" in rendered
    assert (
        "- Benchmark and peer: Peer group data is missing; no peer ranking is fabricated."
        in rendered
    )
    assert (
        "- Fees and redemption: Fee schedule is missing; fee analysis is not fabricated."
        in rendered
    )


def test_all_ok_sections_do_not_append_global_limitations_footer() -> None:
    rendered = render_report_markdown([
        {
            "id": "executive_summary",
            "title": "Executive summary",
            "status": "OK",
            "bullets": ["All required artifacts are present."],
            "data_sources": ["portfolio_summary"],
            "limitations": [],
        }
    ])
    assert "## Executive summary" in rendered
    assert "## Limitations" not in rendered


def test_renderer_does_not_emit_formal_decision_or_action_sections() -> None:
    rendered = render_report_markdown(_sections())
    forbidden_heading_patterns = [
        r"^##\s+Decision\b",
        r"^##\s+ExecutionLedger\b",
        r"^##\s+BUY\b",
        r"^##\s+SELL\b",
        r"^##\s+HOLD\b",
    ]
    for pattern in forbidden_heading_patterns:
        assert re.search(pattern, rendered, flags=re.MULTILINE) is None
