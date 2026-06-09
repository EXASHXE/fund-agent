"""Tests for test support helper documentation consistency."""

from __future__ import annotations

from pathlib import Path

import pytest


SUPPORT_DIR = Path(__file__).resolve().parents[2] / "tests" / "support"


def test_support_readme_exists():
    assert (SUPPORT_DIR / "README.md").exists(), "tests/support/README.md must exist"


def test_error_shape_module_exists():
    assert (SUPPORT_DIR / "error_shape.py").exists(), "tests/support/error_shape.py must exist"


def test_bridge_runner_module_exists():
    assert (SUPPORT_DIR / "bridge_runner.py").exists(), "tests/support/bridge_runner.py must exist"


def test_formal_boundary_module_exists():
    assert (SUPPORT_DIR / "formal_boundary.py").exists(), "tests/support/formal_boundary.py must exist"


def test_error_shape_exports():
    from tests.support.error_shape import (
        assert_all_errors_are_canonical,
        assert_canonical_error,
        assert_envelope_errors_are_canonical,
        assert_top_level_error_is_canonical,
    )


def test_bridge_runner_exports():
    from tests.support.bridge_runner import (
        parse_stdout_json,
        project_root,
        run_bridge_inprocess_json,
        run_bridge_subprocess,
        stdout_text,
        write_temp_json,
    )


def test_formal_boundary_exports():
    from tests.support.formal_boundary import (
        ACTIVE_ACTIONS,
        EMPTY_ANCHOR_REASON_CODES,
        EMPTY_ANCHOR_STATES,
        FAKE_ANCHORS,
        FORMAL_DECISION_ARTIFACT_KEYS,
        PASSIVE_ACTIONS,
        assert_active_decisions_have_anchors,
        assert_no_formal_decision_artifacts,
        assert_passive_empty_anchor_has_structured_justification,
        extract_formal_decisions,
    )


def test_support_modules_no_provider_imports():
    for module_name in ("error_shape", "bridge_runner", "formal_boundary"):
        import importlib
        mod = importlib.import_module(f"tests.support.{module_name}")
        source = Path(mod.__file__).read_text(encoding="utf-8")
        banned = [
            "tavily", "finnhub", "exa", "firecrawl", "akshare",
            "openai", "anthropic", "langchain", "requests", "httpx",
            "aiohttp", "urllib3", "socket",
        ]
        for line in source.splitlines():
            if line.strip().startswith(("import ", "from ")):
                for word in banned:
                    assert word not in line, f"tests.support.{module_name} contains banned import: {word}"
