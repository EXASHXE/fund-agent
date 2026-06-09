"""OpenCode plugin boundary tests."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "opencode.plugin.js"
DOCS = (
    ROOT / "docs" / "host-integrations" / "opencode.md",
    ROOT / "docs" / "START_HERE.md",
    ROOT / "README.md",
)
PROVIDER_SDKS = (
    "tavily",
    "finnhub",
    "exa",
    "firecrawl",
    "reddit",
    "akshare",
    "openai",
    "anthropic",
    "langchain",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _non_comment_js(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("//")
    )


def test_opencode_plugin_does_not_invoke_python_runtime_bridge() -> None:
    text = _text(PLUGIN)
    code = _non_comment_js(text).lower()

    assert "scripts/run_skill.py" not in text
    assert "child_process" not in code
    assert "spawn(" not in code
    assert "exec(" not in code
    assert "execfile" not in code
    assert "python scripts/run_skill.py" not in code
    assert "fund_agent_run_skill" not in code


def test_opencode_plugin_does_not_import_provider_sdks() -> None:
    code = _non_comment_js(_text(PLUGIN)).lower()
    import_lines = [
        line for line in code.splitlines()
        if line.lstrip().startswith("import ") or "require(" in line
    ]

    for provider in PROVIDER_SDKS:
        assert not any(provider in line for line in import_lines), (
            f"opencode plugin imports provider SDK {provider}"
        )


def test_opencode_plugin_exposes_metadata_doc_reader_tools_only() -> None:
    text = _text(PLUGIN)

    assert "fund_agent_skills" in text
    assert "fund_agent_skill_doc" in text
    assert "fund_agent_runtime_hint" in text
    assert "metadata + doc" in text.lower()


def test_opencode_docs_explain_plugin_cannot_execute_python_runtime() -> None:
    combined = "\n".join(_text(path).lower() for path in DOCS)

    assert "metadata + doc-reader" in combined or "metadata + doc reader" in combined
    assert "does not invoke python" in combined or "must not call python" in combined
    assert "cannot provide deterministic python runtime execution" in combined
    assert "source checkout" in combined or "source-checkout" in combined
    assert "scripts/run_skill.py" in combined
