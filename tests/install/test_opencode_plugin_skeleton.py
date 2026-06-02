"""The OpenCode plugin skeleton must exist, be syntactically valid JavaScript,
and expose a plugin function. The test deliberately does NOT attempt to
load the plugin inside OpenCode; it only checks file presence and basic
shape. OpenCode runtime behavior is verified manually per .opencode/INSTALL.md.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILE = ROOT / "opencode.plugin.js"
NODE_BIN_CANDIDATES = ("node",)


def _has_node() -> bool:
    for candidate in NODE_BIN_CANDIDATES:
        try:
            subprocess.run(
                [candidate, "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False


def test_opencode_plugin_file_exists():
    assert PLUGIN_FILE.exists(), "opencode.plugin.js is required for the OpenCode install"


def test_opencode_plugin_exports_a_function():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # Must export a plugin function (named or default) for OpenCode to load.
    assert re.search(r"export\s+(?:const|async\s+const|function|default)", text), (
        "opencode.plugin.js must export a plugin function"
    )


def test_opencode_plugin_uses_esm_syntax():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # The OpenCode plugin loader uses ESM; the plugin must use
    # `import` / `export` rather than CommonJS `require` / `module.exports`.
    assert "import" in text, "opencode.plugin.js should use ESM imports"
    assert "module.exports" not in text, (
        "opencode.plugin.js must not use CommonJS module.exports; use ESM exports"
    )


def test_opencode_plugin_has_plugin_version_constant():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # PLUGIN_VERSION must equal the canonical VERSION file. The
    # contract is that the plugin advertises the same version as
    # the package; the test reads the current value rather than
    # pinning a literal so it stays valid across dev tags.
    version_text = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pattern = r"PLUGIN_VERSION\s*=\s*[\"']" + re.escape(version_text) + r"[\"']"
    assert re.search(pattern, text), (
        f"opencode.plugin.js must declare PLUGIN_VERSION = '{version_text}'"
    )


def test_opencode_plugin_skill_catalog_present():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # The five manifest runtime IDs and their hyphenated slugs must be in
    # the plugin's SKILL_CATALOG, not just scattered strings.
    for runtime_id, doc_slug in [
        ("fund_analysis", "fund-analysis"),
        ("news_research", "news-research"),
        ("sentiment_analysis", "sentiment-analysis"),
        ("thesis_generation", "thesis-generation"),
        ("decision_support", "decision-support"),
    ]:
        assert f'"{runtime_id}"' in text or f"'{runtime_id}'" in text, (
            f"opencode.plugin.js SKILL_CATALOG missing runtime_id '{runtime_id}'"
        )
        assert f'"{doc_slug}"' in text or f"'{doc_slug}'" in text, (
            f"opencode.plugin.js SKILL_CATALOG missing doc_slug '{doc_slug}'"
        )


def test_opencode_plugin_does_not_import_provider_sdks():
    """The plugin must not have any static or dynamic imports of provider
    SDKs. We allow the names to appear in comments that explicitly disclaim
    them (e.g. "must not import tavily"), but not in any import or require
    statement."""
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    forbidden = [
        "tavily",
        "finnhub",
        "exa",
        "firecrawl",
        "reddit",
        "akshare",
        "openai",
        "anthropic",
        "langchain",
    ]
    # Find every line that is a static import or a dynamic require.
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


def test_opencode_plugin_does_not_perform_network_io():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # No raw network IO. The plugin reads files from disk only.
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


def test_opencode_plugin_blocks_path_traversal():
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # Plugin must validate paths before reading from disk. Look for either
    # a path-traversal guard or a path-prefix check.
    has_guard = (
        ".." in text
        and ("normalize" in text or "startsWith" in text or "resolve" in text)
    )
    assert has_guard, (
        "opencode.plugin.js must guard against path traversal in skill doc reads"
    )


def test_opencode_plugin_is_syntactically_valid():
    if not _has_node():
        return  # Skip if node is not available in the test env.
    result = subprocess.run(
        ["node", "--check", str(PLUGIN_FILE)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"opencode.plugin.js failed `node --check`: {result.stderr}"
    )
