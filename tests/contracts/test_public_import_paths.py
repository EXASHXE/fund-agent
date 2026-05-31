"""Public import path stability tests."""

from __future__ import annotations

import importlib

from src.skillpack.loader import load_skillpack_manifest


PUBLIC_IMPORTS = [
    ("src.schemas.skill", "SkillInput"),
    ("src.schemas.skill", "SkillOutput"),
    ("src.schemas.skill", "SkillError"),
    ("src.schemas.evidence", "EvidenceItem"),
    ("src.schemas.evidence_graph", "EvidenceGraph"),
    ("src.schemas.decision", "Decision"),
    ("src.schemas.decision", "ExecutionLedger"),
    ("src.tools.evidence.validators", "compile_evidence_graph"),
    ("src.tools.evidence.builders", "build_hard_evidence_from_metric"),
    ("src.tools.evidence.builders", "build_soft_evidence_from_mcp_result"),
    ("src.tools.adapters.mcp", "MCPHostAdapter"),
    ("src.tools.adapters.mcp", "InMemoryMCPHostAdapter"),
    ("src.skills_runtime.fund_analysis", "FundAnalysisSkill"),
    ("src.skills_runtime.news_research", "NewsResearchSkill"),
    ("src.skills_runtime.sentiment_analysis", "SentimentAnalysisSkill"),
    ("src.skills_runtime.thesis_generation", "ThesisGenerationSkill"),
    ("src.skills_runtime.decision_support", "DecisionSupportSkill"),
    ("src.skillpack.loader", "load_skillpack_manifest"),
    ("src.skillpack.loader", "resolve_runtime"),
]


def test_public_import_paths_resolve():
    for module_name, attr_name in PUBLIC_IMPORTS:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} not found"


def test_manifest_runtime_paths_are_public_import_paths():
    manifest = load_skillpack_manifest()
    for skill in manifest.skills:
        module_name, attr_name = skill.runtime.split(":", 1)
        module = importlib.import_module(module_name)
        value = module
        for part in attr_name.split("."):
            value = getattr(value, part)
        assert value is not None, f"Failed to resolve {skill.name}: {skill.runtime}"
