"""Tests for the fund_agent public facade.

Asserts:
- Public imports work
- Provider facade does not import provider SDKs or network clients
- Quality facade works
- Regression facade can list fixtures
- Old deep imports still work
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestFundAgentInit:
    def test_import_package(self):
        from src.fund_agent import __version__
        assert isinstance(__version__, str)
        assert __version__ != "0.0.0"


class TestWorkflowFacade:
    def test_import_workflow(self):
        from src.fund_agent.workflow import (
            WorkflowTrace,
            classify_advisory_intent,
            build_evidence_graph_from_workflow,
            compose_advisory_workflow_report,
        )
        assert WorkflowTrace is not None
        assert callable(classify_advisory_intent)

    def test_workflow_trace_creation(self):
        from src.fund_agent.workflow import WorkflowTrace
        trace = WorkflowTrace(scenario_id="test")
        trace.add_event("TEST", "hello")
        d = trace.to_dict()
        assert d["scenario_id"] == "test"
        assert len(d["events"]) == 1

    def test_classify_intent(self):
        from src.fund_agent.workflow import classify_advisory_intent
        result = classify_advisory_intent(user_question="给我出一份基金报告")
        assert isinstance(result, list)


class TestRegressionFacade:
    def test_import_regression(self):
        from src.fund_agent.regression import (
            list_personal_regression_fixtures,
            PersonalRegressionResult,
        )
        assert callable(list_personal_regression_fixtures)

    def test_list_fixtures(self):
        from src.fund_agent.regression import list_personal_regression_fixtures
        fixtures = list_personal_regression_fixtures()
        assert isinstance(fixtures, list)
        if fixtures:
            assert all(isinstance(p, Path) for p in fixtures)
            assert all(p.suffix == ".json" for p in fixtures)


class TestQualityFacade:
    def test_import_quality(self):
        from src.fund_agent.quality import (
            evaluate_advisory_quality_gate,
            FORBIDDEN_EXECUTION_FIELDS,
        )
        assert callable(evaluate_advisory_quality_gate)
        assert isinstance(FORBIDDEN_EXECUTION_FIELDS, frozenset)
        assert "broker_order_id" in FORBIDDEN_EXECUTION_FIELDS


class TestProvidersFacade:
    def test_import_providers(self):
        from src.fund_agent.providers import (
            ProviderCapability,
            ProviderConfig,
            ProviderCredentialSpec,
            ProviderCredentials,
            ProviderRegistry,
            ProviderResult,
            compare_provider_results,
            select_provider_order,
        )
        assert ProviderCapability.FUND_NAV_HISTORY is not None

    def test_no_provider_sdk_imports(self):
        import src.fund_agent.providers as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        forbidden = ("tavily", "finnhub", "firecrawl",
                      "reddit", "openai", "anthropic", "langchain")
        for name in forbidden:
            assert name not in source.lower(), f"providers facade imports {name}"

    def test_no_network_imports(self):
        import src.fund_agent.providers as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib3" not in source

    def test_registry_creation(self):
        from src.fund_agent.providers import ProviderRegistry, ProviderConfig
        reg = ProviderRegistry()
        assert reg.list_providers() == []


class TestReportingFacade:
    def test_import_reporting(self):
        from src.fund_agent.reporting import (
            compose_advisory_workflow_report,
            compute_report_status,
            data_completeness_grade,
        )
        assert callable(compose_advisory_workflow_report)


class TestRuntimeFacade:
    def test_import_runtime(self):
        from src.fund_agent.runtime import (
            FundAnalysisSkill,
            DecisionSupportSkill,
            SkillInput,
            SkillOutput,
        )
        assert FundAnalysisSkill is not None
        assert DecisionSupportSkill is not None


class TestVersionFacade:
    def test_version_matches_file(self):
        from src.fund_agent.version import __version__
        version_file = ROOT / "VERSION"
        if version_file.exists():
            expected = version_file.read_text(encoding="utf-8").strip()
            assert __version__ == expected


class TestOldDeepImportsStillWork:
    def test_old_workflow_import(self):
        from src.skills_runtime.workflow import WorkflowTrace
        assert WorkflowTrace is not None

    def test_old_host_data_import(self):
        from src.host_data import ProviderConfig, ProviderResult
        assert ProviderConfig is not None

    def test_old_quality_gate_import(self):
        from src.tools.workflow.advisory_quality_gate import evaluate_advisory_quality_gate
        assert callable(evaluate_advisory_quality_gate)

    def test_old_provider_config_import(self):
        from src.host_data.provider_config import ProviderCredentialSpec
        assert ProviderCredentialSpec is not None
