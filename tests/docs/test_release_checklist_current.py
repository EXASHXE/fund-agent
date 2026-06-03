"""Tests that the release checklist is current and does not
contain misleading historical version-specific checks.

Guards:

- ``docs/release-checklist.md`` must not contain active checklist
  assertions for old fixed versions (0.4.0.dev0, 0.4.6, 0.4.7-dev).
- Historical version-specific sections are acceptable only in
  ``docs/archive/release-checklists.md`` or explicitly labeled
  as historical.
- The current checklist must reference the archive for historical
  sections.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CURRENT_CHECKLIST = ROOT / "docs" / "release-checklist.md"
ARCHIVE_CHECKLIST = ROOT / "docs" / "archive" / "release-checklists.md"

# Fixed version strings that should NOT appear as active checklist
# assertions in the current checklist.
FIXED_OLD_VERSIONS = (
    "0.4.0.dev0",
    "0.4.3",
    "0.4.5",
    "0.4.6",
    "0.4.7-dev",
)


def test_current_checklist_has_no_fixed_version_assertions():
    """The current release checklist must not contain active
    checklist items that assert fixed old version strings."""
    assert CURRENT_CHECKLIST.exists()
    text = CURRENT_CHECKLIST.read_text(encoding="utf-8")

    # Find checklist items (lines starting with "- [ ]" within sections)
    lines = text.splitlines()
    # Also check for inline checklist items that may be nested
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        for old_ver in FIXED_OLD_VERSIONS:
            assert old_ver not in stripped, (
                f"Current release checklist contains stale version check: "
                f"{stripped!r} (contains {old_ver!r}). "
                f"Historical checks must live in {ARCHIVE_CHECKLIST}."
            )


def test_current_checklist_references_archive():
    """The current checklist must point to the archive for historical
    checklist sections."""
    text = CURRENT_CHECKLIST.read_text(encoding="utf-8").lower()
    assert "archive/release-checklists.md" in text or "historical" in text, (
        "Current release checklist must reference the historical archive "
        f"({ARCHIVE_CHECKLIST})"
    )


def test_archive_checklist_exists():
    """The historical release checklists archive must exist."""
    assert ARCHIVE_CHECKLIST.exists(), (
        f"Archive checklist missing: {ARCHIVE_CHECKLIST}"
    )


def test_archive_checklist_is_marked_historical():
    """The archive must clearly state it is historical / reference-only."""
    text = ARCHIVE_CHECKLIST.read_text(encoding="utf-8").lower()
    assert "historical" in text, (
        "Archive checklist must clearly mark itself as historical"
    )
    assert "do not" in text and "apply" in text or "not the current" in text, (
        "Archive checklist must warn not to apply to current release"
    )
