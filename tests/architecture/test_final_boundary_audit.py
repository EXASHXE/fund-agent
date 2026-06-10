"""Final boundary audit for pre-release readiness.

Static assertions ensuring no provider SDKs, network clients, broker/order
execution machinery, or deprecated surfaces exist in runtime plugin core.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import (
    BROKER_KEYWORDS,
    DEPRECATED_SRC_MODULES,
    DEPRECATED_SRC_PATHS,
    NETWORK_CLIENTS,
    PLUGIN_CORE_DIRS,
    PROVIDER_SDKS,
    ROOT,
    SRC,
    imports_from_dir,
    imports_from_file,
)


def test_no_provider_sdks_in_skills_runtime(plugin_imports):
    violations = plugin_imports["skills_runtime"] & PROVIDER_SDKS
    assert not violations, f"skills_runtime imports provider SDKs: {violations}"


def test_no_provider_sdks_in_skillpack(plugin_imports):
    violations = plugin_imports["skillpack"] & PROVIDER_SDKS
    assert not violations, f"skillpack imports provider SDKs: {violations}"


def test_no_provider_sdks_in_tools(plugin_imports):
    violations = plugin_imports["tools"] & PROVIDER_SDKS
    assert not violations, f"tools imports provider SDKs: {violations}"


def test_no_network_clients_in_skills_runtime(plugin_imports):
    violations = plugin_imports["skills_runtime"] & NETWORK_CLIENTS
    assert not violations, f"skills_runtime imports network clients: {violations}"


def test_no_network_clients_in_skillpack(plugin_imports):
    violations = plugin_imports["skillpack"] & NETWORK_CLIENTS
    assert not violations, f"skillpack imports network clients: {violations}"


def test_no_broker_keywords_in_runtime_source(runtime_source_texts):
    for relpath, text in runtime_source_texts.items():
        lower = text.lower()
        for kw in BROKER_KEYWORDS:
            assert kw not in lower, f"{relpath} contains broker keyword: {kw}"


def test_opencode_plugin_does_not_invoke_python_or_child_process():
    js = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")
    for kw in ("child_process", "execFile", "execSync", "spawn(", "exec(",
               'spawnSync', 'python3', 'sys.executable'):
        assert kw not in js, f"opencode.plugin.js contains execution keyword: {kw}"


def test_fund_analysis_does_not_import_decision(plugin_imports):
    fa_imports = imports_from_dir(SRC / "skills_runtime" / "fund_analysis")
    assert "src.schemas.decision" not in fa_imports, (
        "fund_analysis must not import Decision schema"
    )


def test_thesis_generation_does_not_import_decision():
    imports = imports_from_file(
        SRC / "skills_runtime" / "thesis_generation.py"
    )
    assert "src.schemas.decision" not in imports, (
        "thesis_generation must not import Decision schema"
    )


def test_decision_support_allowed_to_import_decision():
    imports = imports_from_dir(SRC / "skills_runtime" / "decision_support")
    assert "src.schemas.decision" in imports, (
        "decision_support should import Decision schema"
    )


def test_deprecated_src_surfaces_remain_absent():
    for relpath in DEPRECATED_SRC_MODULES:
        parts = relpath.split(".")
        parts[0] = "src"
        abs_path = ROOT.joinpath(*parts)
        assert not abs_path.exists(), f"Deprecated surface still present: {relpath}"


def test_no_deprecated_surface_imports_in_plugin_core(plugin_imports):
    for dirname in PLUGIN_CORE_DIRS:
        imports = plugin_imports[dirname]
        for deprecated in DEPRECATED_SRC_MODULES:
            violations = [i for i in imports if i.startswith(deprecated)]
            assert not violations, (
                f"src/{dirname} imports deprecated {deprecated}: {violations}"
            )
