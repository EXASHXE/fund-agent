"""Host-facing command and boundary consistency tests."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = (
    ROOT / "docs" / "START_HERE.md",
    ROOT / "README.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "host-integrations" / "README.md",
    ROOT / "docs" / "host-readiness-matrix.md",
    ROOT / "docs" / "external-host-smoke-commands.md",
)
DEPRECATED_SRC_SURFACES = (
    "src/core",
    "src/infra",
    "src/workflows",
    "src/config",
    "src/data",
    "src/db",
    "src/kg",
    "src/vectorstore",
    "src.core",
    "src.infra",
    "src.workflows",
    "src.config",
    "src.data",
    "src.db",
    "src.kg",
    "src.vectorstore",
    "src/cli.py",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_text() -> str:
    return "\n".join(_text(path) for path in DOCS)


COMMAND_DOCS = (
    ROOT / "docs" / "START_HERE.md",
    ROOT / "README.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "external-host-smoke-commands.md",
)


def test_docs_reference_runtime_bridge_script_not_deprecated_cli() -> None:
    for path in COMMAND_DOCS:
        text = _text(path)
        assert "scripts/run_skill.py" in text, f"{path} should show runtime bridge path"
        assert "src/cli.py" not in text


def test_docs_runtime_bridge_commands_point_to_existing_fixture_files() -> None:
    for path in DOCS:
        text = _text(path)
        for relpath in sorted(set(re.findall(r"examples/[A-Za-z0-9_./-]+\.json", text))):
            assert (ROOT / relpath).is_file(), f"{path} references missing fixture {relpath}"


def test_start_here_links_point_to_existing_repo_files() -> None:
    start_here = ROOT / "docs" / "START_HERE.md"
    text = _text(start_here)
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        rel = target.split("#", 1)[0]
        if not rel:
            continue
        assert (start_here.parent / rel).resolve().exists(), (
            f"START_HERE link target does not exist: {target}"
        )


def test_docs_mention_python_311_for_source_checkout_runtime() -> None:
    for path in COMMAND_DOCS:
        text = _text(path)
        assert "Python 3.11+" in text or "python (3.11+)" in text or ">=3.11" in text, (
            f"{path} should mention Python 3.11+ for runtime execution"
        )


def test_docs_state_plugin_and_runtime_bridge_boundaries() -> None:
    text = _all_text().lower()
    assert "opencode plugin" in text
    assert "metadata + doc-reader" in text or "metadata + doc reader" in text
    assert "runtime bridge" in text
    assert "source-checkout" in text or "source checkout" in text
    assert "manual-host" in text or "manual host" in text


def test_docs_state_host_owns_external_concerns() -> None:
    text = _all_text().lower()
    for phrase in (
        "host owns",
        "data fetching",
        "provider sdk",
        "network access",
        "credentials",
        "final ux",
    ):
        assert phrase in text


def test_docs_state_formal_decision_boundaries() -> None:
    text = _all_text().lower()
    assert "fund_analysis" in text
    assert "thesis_generation" in text
    assert "does not" in text
    assert "decision_support" in text
    assert "only" in text
    assert "decision" in text
    assert "executionledger" in text or "executionledger" in text.replace(" ", "")


def test_docs_do_not_describe_deprecated_src_surfaces_as_current() -> None:
    for path in DOCS:
        text = _text(path)
        for term in DEPRECATED_SRC_SURFACES:
            assert term not in text, f"{path} references deprecated surface {term}"


def test_readme_and_start_here_do_not_recommend_legacy_fund_analyst_slug() -> None:
    for path in (ROOT / "README.md", ROOT / "docs" / "START_HERE.md"):
        text = _text(path).lower()
        assert "fund-analyst runtime" not in text
        assert "skills/fund-analyst" not in text
        assert "use fund-analyst" not in text
        assert "load fund-analyst" not in text
