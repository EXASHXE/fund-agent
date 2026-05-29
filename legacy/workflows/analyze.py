"""Orchestration entry for fund analysis workflow.
Delegates to src.core.workflow.run_analyze.
"""
from __future__ import annotations


def run_analyze(args, keyword_callback=None):
    """Run the full fund analysis workflow.
    
    This is the primary entry point for the AI Financial Research OS.
    Delegates to the core workflow implementation.
    """
    from legacy.workflows.workflow import run_analyze as _run
    return _run(args)
