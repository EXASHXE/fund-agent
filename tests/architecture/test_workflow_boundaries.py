"""Architecture boundary tests for the workflow layer split.

Asserts that ``src/tools/workflow`` (pure tools) does not import from
``src/skills_runtime`` (runtime orchestration), keeping the layer
dependency direction one-way: runtime may use tools, but tools must not
depend on runtime.

The public facade ``src/fund_agent/workflow.py`` is allowed to import from
both layers since its role is precisely to compose them into a stable API.
"""

from __future__ import annotations

import pytest

from .conftest import SRC, imports_from_dir, imports_from_file

TOOLS_WORKFLOW = SRC / "tools" / "workflow"
RUNTIME_WORKFLOW = SRC / "skills_runtime" / "workflow"
FACADE_WORKFLOW = SRC / "fund_agent" / "workflow.py"


def test_tools_workflow_does_not_import_skills_runtime():
    """src/tools/workflow must not import from src.skills_runtime."""
    imports = imports_from_dir(TOOLS_WORKFLOW)
    violations = {i for i in imports if i.startswith("src.skills_runtime")}
    assert not violations, (
        f"src/tools/workflow imports from skills_runtime (reverse dependency): {violations}"
    )


def test_tools_workflow_does_not_import_evidence_bridge():
    """Specifically guard against re-exporting evidence_bridge helpers."""
    imports = imports_from_dir(TOOLS_WORKFLOW)
    assert "src.skills_runtime.workflow.evidence_bridge" not in imports, (
        "src/tools/workflow must not import evidence_bridge from skills_runtime"
    )


def test_runtime_workflow_may_import_tools():
    """src/skills_runtime/workflow is allowed to import from src.tools.workflow.

    This documents the allowed direction: runtime -> tools, not tools -> runtime.
    """
    imports = imports_from_dir(RUNTIME_WORKFLOW)
    _ = {i for i in imports if i.startswith("src.tools.workflow")}


def test_public_facade_imports_both_layers():
    """src/fund_agent/workflow.py is the composition point for both layers."""
    imports = imports_from_file(FACADE_WORKFLOW)
    assert any(i.startswith("src.skills_runtime.workflow") for i in imports), (
        "public facade should import from skills_runtime.workflow"
    )
    assert any(i.startswith("src.tools.workflow") for i in imports), (
        "public facade should import from tools.workflow"
    )


def test_tools_workflow_init_has_no_runtime_reexport():
    """The tools/workflow __init__ must not re-export runtime symbols."""
    init = TOOLS_WORKFLOW / "__init__.py"
    assert init.is_file(), "src/tools/workflow/__init__.py must exist"
    imports = imports_from_file(init)
    violations = {i for i in imports if i.startswith("src.skills_runtime")}
    assert not violations, (
        f"src/tools/workflow/__init__.py imports from skills_runtime: {violations}"
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "compose_advisory_workflow_report",
        "WorkflowTrace",
        "classify_advisory_intent",
        "build_evidence_graph_from_workflow",
        "AdvisoryIntent",
    ],
)
def test_public_facade_exports_stable_symbols(symbol):
    """The public facade must continue exporting these stable symbols."""
    imports = imports_from_file(FACADE_WORKFLOW)
    assert any(i.startswith("src.skills_runtime.workflow") or i.startswith("src.tools.workflow")
               for i in imports), "facade imports present"
    # Re-read the source to confirm the symbol is in __all__ or imported.
    text = FACADE_WORKFLOW.read_text(encoding="utf-8")
    assert symbol in text, (
        f"public facade src/fund_agent/workflow.py must reference symbol: {symbol}"
    )
