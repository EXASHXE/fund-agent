"""Examples checker script tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "check_examples.py"


def test_check_examples_script_exists():
    assert SCRIPT.exists()


def test_check_examples_script_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"


def test_check_examples_script_does_not_reference_research_os():
    content = SCRIPT.read_text(encoding="utf-8")

    # The script may reference ResearchOS only as a forbidden check pattern
    if "src.core.research_os" in content:
        lines_with_ref = [i for i, line in enumerate(content.split("\n"), 1) if "src.core.research_os" in line]
        for lineno in lines_with_ref:
            line = content.split("\n")[lineno - 1]
            assert "research_os" in line.lower(), f"Unexpected: {line}"
    # Script should not import or call ResearchOS
    assert "import research_os" not in content.lower()
    assert "from src.core.research_os" not in content
    assert "call ResearchOS" not in content or "not call" in content.lower()
