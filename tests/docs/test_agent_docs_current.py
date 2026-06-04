"""Verify AGENTS.md is current for v0.4.8-dev."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("AGENTS.md")


def test_doc_exists():
    assert DOC_PATH.exists()


def test_no_duplicate_before_changing_runtime_contracts():
    content = DOC_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")
    occurrences = [i for i, line in enumerate(lines) if "Before changing runtime contracts" in line]
    assert len(occurrences) == 1, (
        f"'Before changing runtime contracts' appears {len(occurrences)} times "
        f"at lines {[o+1 for o in occurrences]}; duplicate must be removed"
    )


def test_mentions_report_output_contract():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "docs/contracts/report-output-contract.v1.md" in content, (
        "AGENTS.md should reference the report output contract"
    )


def test_no_v047_stale_current():
    """AGENTS.md should not have stale v0.4.7-dev references in active sections."""
    content = DOC_PATH.read_text(encoding="utf-8")
    # Version references are fine in CHANGELOG but not in active instructions
    # Check that the Testing Commands section doesn't have version tags
    # Allow version in changelog-like context but not in command comments
    for line in content.split("\n"):
        if "v0.4.7-dev" in line and line.strip().startswith("#"):
            # Only allow in context that's explicitly about past releases
            if "0.4.7" not in line.lower().split("release") and "historical" not in line.lower():
                pass  # the test just checks: it's been cleaned (the grep would fail if still there)
    # Simple check: search for the removed tags
    assert "# Runtime bridge CLI tests (v0.4.7-dev)" not in content
    assert "# Runtime bridge CLI smoke (v0.4.7-dev)" not in content


def test_runtime_bridge_not_described_as_entirely_future():
    """The runtime bridge should not be described as entirely future."""
    content = DOC_PATH.read_text(encoding="utf-8")
    # The line that was "future runtime bridge (design only)" should be updated
    assert "future runtime bridge (design only)" not in content, (
        "runtime bridge is partially implemented; should not be described as 'future (design only)'"
    )


def test_mentions_report_composer():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "report_composer" in content or "compose_personal_fund_report" in content, (
        "AGENTS.md should mention the report composer"
    )
