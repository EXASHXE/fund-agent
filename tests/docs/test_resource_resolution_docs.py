"""Docs tests for resource resolution documentation.

Verifies that documentation accurately describes the resource resolver,
off-repo current working directory support, and supported execution modes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

DOCS_TO_CHECK = [
    ROOT / "docs" / "START_HERE.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "install" / "manual-host.md",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _text_lower(path: Path) -> str:
    return _text(path).lower()


class TestResourceResolutionDocsExist:
    def test_resources_module_exists(self):
        assert (ROOT / "src" / "skillpack" / "resources.py").exists()


class TestDocsMentionExecutionModes:
    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_fund_agent_run_skill(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "fund-agent-run-skill" in text, (
            f"{doc_path.name} must mention fund-agent-run-skill console script"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_python_m_src_skillpack_run_skill(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text(doc_path)
        assert "src.skillpack.run_skill" in text, (
            f"{doc_path.name} must mention python -m src.skillpack.run_skill"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_scripts_run_skill(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text(doc_path)
        assert "scripts/run_skill.py" in text, (
            f"{doc_path.name} must mention scripts/run_skill.py"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_source_checkout(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "source checkout" in text or "git clone" in text, (
            f"{doc_path.name} must mention source checkout"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_editable_install(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "pip install -e ." in text or "editable install" in text, (
            f"{doc_path.name} must mention editable install"
        )


class TestDocsMentionOffRepoCwdSupport:
    def test_start_here_mentions_off_repo_or_resource_resolver(self):
        text = _text_lower(ROOT / "docs" / "START_HERE.md")
        needles = [
            "non-repo",
            "off-repo",
            "resource resolver",
            "outside the repo",
            "package root",
        ]
        assert any(n in text for n in needles), (
            "docs/START_HERE.md must mention off-repo cwd support or resource resolver"
        )

    def test_runtime_bridge_cli_mentions_off_repo_cwd(self):
        text = _text_lower(ROOT / "docs" / "install" / "runtime-bridge-cli.md")
        needles = [
            "non-repo",
            "off-repo",
            "outside the repo",
            "resource resolver",
            "current working directory",
        ]
        assert any(n in text for n in needles), (
            "docs/install/runtime-bridge-cli.md must mention off-repo cwd support"
        )

    def test_manual_host_mentions_off_repo_cwd(self):
        text = _text_lower(ROOT / "docs" / "install" / "manual-host.md")
        needles = [
            "non-repo",
            "off-repo",
            "outside the repo",
            "resource resolver",
            "current working directory",
        ]
        assert any(n in text for n in needles), (
            "docs/install/manual-host.md must mention off-repo cwd support"
        )

    @pytest.mark.parametrize("doc_path", [
        ROOT / "docs" / "install" / "runtime-bridge-cli.md",
        ROOT / "docs" / "install" / "manual-host.md",
    ])
    def test_mentions_absolute_input_paths(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "absolute" in text, (
            f"{doc_path.name} must mention absolute input paths for off-repo examples"
        )


class TestDocsMentionBoundaryRules:
    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_host_owns_data_providers(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        needles = ["host owns", "host-driven", "host injects", "external host"]
        assert any(n in text for n in needles), (
            f"{doc_path.name} must state that the host owns data fetching/provider SDKs"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_opencode_plugin_metadata_doc_reader_only(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "metadata" in text and "doc" in text, (
            f"{doc_path.name} must describe OpenCode plugin as metadata + doc-reader"
        )

    def test_no_wheel_only_claim(self):
        for doc_path in DOCS_TO_CHECK:
            if not doc_path.exists():
                continue
            text = _text_lower(doc_path)
            assert "wheel-only" not in text.replace("not yet tested", ""), (
                f"{doc_path.name} must not claim wheel-only support without tests"
            )
