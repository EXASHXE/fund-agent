"""Tests for docs/external-host-smoke-commands.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE_DOC = ROOT / "docs" / "external-host-smoke-commands.md"


def _text() -> str:
    return SMOKE_DOC.read_text(encoding="utf-8").lower()


def test_smoke_doc_exists():
    assert SMOKE_DOC.is_file()


def test_smoke_doc_referenced_fixtures_exist():
    text = SMOKE_DOC.read_text(encoding="utf-8")
    for relpath in set(re.findall(r"(examples/[A-Za-z0-9_./-]+\.json)", text)):
        assert (ROOT / relpath).is_file(), f"smoke doc references missing fixture: {relpath}"


def test_smoke_doc_uses_run_skill_py():
    text = SMOKE_DOC.read_text(encoding="utf-8")
    assert "scripts/run_skill.py" in text
    assert "src/cli.py" not in text


def test_smoke_doc_mentions_fake_sample_data_only():
    text = _text()
    assert "fake" in text or "sample" in text


def test_smoke_doc_mentions_host_owned_mcp():
    text = _text()
    assert "host owns" in text or "host-owned" in text


def test_smoke_doc_mentions_no_broker_execution():
    text = _text()
    assert "no broker" in text


def test_smoke_doc_mentions_opencode_plugin_boundary():
    text = SMOKE_DOC.read_text(encoding="utf-8").lower()
    stripped = text.replace("\n", " ")
    assert "not invoke python" in stripped or "does not invoke python" in stripped


def test_smoke_doc_all_json_references_exist():
    text = SMOKE_DOC.read_text(encoding="utf-8")
    for relpath in set(re.findall(r"examples/[A-Za-z0-9_./-]+\.json", text)):
        assert (ROOT / relpath).is_file(), f"missing: {relpath}"
