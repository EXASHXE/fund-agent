"""OpenCode plugin runtime boundary tests.

Asserts that the OpenCode plugin remains metadata + doc-reader only and
does not invoke Python, spawn subprocesses, or reference the runtime
bridge CLI as an executable action.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILE = ROOT / "opencode.plugin.js"
PACKAGE_JSON = ROOT / "package.json"


def _plugin_source() -> str:
    return PLUGIN_FILE.read_text(encoding="utf-8")


def _package_json() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


class TestPluginDoesNotSpawnPython:
    def test_plugin_does_not_import_child_process(self):
        text = _plugin_source()
        assert "child_process" not in text, (
            "opencode.plugin.js must not import child_process"
        )

    def test_plugin_does_not_reference_run_skill_as_executable(self):
        text = _plugin_source()
        assert "scripts/run_skill.py" not in text, (
            "opencode.plugin.js must not reference scripts/run_skill.py as executable"
        )

    def test_plugin_does_not_spawn_python_subprocess(self):
        text = _plugin_source()
        forbidden = [
            "spawn(",
            "exec(",
            "execFile(",
            "execSync(",
            "spawnSync(",
        ]
        for pattern in forbidden:
            assert pattern not in text, (
                f"opencode.plugin.js must not use {pattern} for subprocess spawning"
            )


class TestPluginDoesNotClaimNpmRunsPython:
    def test_package_json_does_not_claim_npm_runs_python_runtime(self):
        data = _package_json()
        scripts = data.get("scripts", {})
        for name, value in scripts.items():
            assert "run_skill" not in str(value), (
                f"package.json script '{name}' must not reference run_skill"
            )
            assert "python" not in str(value).lower(), (
                f"package.json script '{name}' must not invoke Python"
            )

    def test_package_json_main_is_js_only(self):
        data = _package_json()
        main = data.get("main", "")
        assert main.endswith(".js"), (
            f"package.json main must be a .js file, got {main!r}"
        )

    def test_package_json_exports_are_js_only(self):
        data = _package_json()
        exports = data.get("exports", {})
        if isinstance(exports, dict):
            for key, value in exports.items():
                if isinstance(value, str):
                    assert value.endswith(".js"), (
                        f"package.json exports['{key}'] must be .js, got {value!r}"
                    )


class TestPluginMetadataDocReaderOnly:
    def test_plugin_comment_says_metadata_doc_reader_only(self):
        text = _plugin_source()
        assert "metadata" in text.lower() and "doc" in text.lower(), (
            "opencode.plugin.js must describe itself as metadata + doc-reader"
        )

    def test_plugin_does_not_import_provider_sdks(self):
        text = _plugin_source()
        forbidden = [
            "tavily", "finnhub", "exa", "firecrawl", "reddit",
            "akshare", "openai", "anthropic", "langchain",
        ]
        import_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                import_lines.append(line)
            if "require(" in stripped and not stripped.startswith("//"):
                import_lines.append(line)
        import_blob = "\n".join(import_lines)
        for sdk in forbidden:
            assert sdk not in import_blob.lower(), (
                f"opencode.plugin.js must not import provider SDK '{sdk}'"
            )

    def test_plugin_does_not_perform_network_io(self):
        text = _plugin_source()
        forbidden_patterns = [
            re.compile(r"\bfetch\s*\("),
            re.compile(r"\bXMLHttpRequest\b"),
            re.compile(r"\bhttp\.request\s*\("),
            re.compile(r"\bhttps\.request\s*\("),
            re.compile(r"\baxios\."),
        ]
        for pat in forbidden_patterns:
            assert not pat.search(text), (
                f"opencode.plugin.js must not perform network IO (matched {pat.pattern})"
            )


class TestOpenCodeInstallDocsMetadataOnly:
    def test_opencode_install_doc_says_metadata_only(self):
        install_doc = ROOT / ".opencode" / "INSTALL.md"
        if not install_doc.exists():
            pytest.skip(".opencode/INSTALL.md not found")
        text = install_doc.read_text(encoding="utf-8").lower()
        assert "metadata" in text or "doc-reader" in text or "doc reader" in text, (
            ".opencode/INSTALL.md must say the plugin is metadata/doc-reader only"
        )

    def test_opencode_install_doc_does_not_claim_python_execution(self):
        install_doc = ROOT / ".opencode" / "INSTALL.md"
        if not install_doc.exists():
            pytest.skip(".opencode/INSTALL.md not found")
        text = install_doc.read_text(encoding="utf-8").lower()
        forbidden = [
            "plugin runs python",
            "plugin invokes python",
            "plugin executes python",
            "plugin calls python",
        ]
        for phrase in forbidden:
            assert phrase not in text, (
                f".opencode/INSTALL.md must not claim: {phrase!r}"
            )
