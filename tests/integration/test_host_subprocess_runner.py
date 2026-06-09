"""Host subprocess runner integration tests.

Tests:
- examples/host_subprocess_runner.py exists.
- It does not import src.skills_runtime or runtime skill classes.
- It does not import provider SDKs or network clients.
- run_json_skill works for fund_analysis fixture.
- run_json_skill works for decision_support fixture.
- run_json_skill works for thesis_generation fixture.
- run_markdown_report returns Markdown and not JSON.
- Module docstring mentions host owns data fetching/provider integration
  and fake/sample fixtures.
- The example does not claim broker/order execution.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "examples" / "host_subprocess_runner.py"


def _read_runner() -> str:
    assert RUNNER_PATH.exists(), f"host_subprocess_runner.py not found at {RUNNER_PATH}"
    return RUNNER_PATH.read_text(encoding="utf-8")


def _get_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


class TestHostRunnerExists:
    def test_runner_file_exists(self):
        assert RUNNER_PATH.exists()

    def test_runner_is_python(self):
        assert RUNNER_PATH.suffix == ".py"


class TestHostRunnerNoRuntimeImports:
    def test_does_not_import_skills_runtime(self):
        source = _read_runner()
        imports = _get_imports(source)
        violations = [i for i in imports if "skills_runtime" in i]
        assert not violations, f"host_subprocess_runner imports skills_runtime: {violations}"

    def test_does_not_import_runtime_skill_classes(self):
        source = _read_runner()
        for forbidden in ("FundAnalysisSkill", "DecisionSupportSkill", "ThesisGenerationSkill"):
            assert forbidden not in source, f"host_subprocess_runner references {forbidden}"


class TestHostRunnerNoProviderSDKs:
    def test_does_not_import_provider_sdks(self):
        source = _read_runner()
        imports = _get_imports(source)
        provider_keywords = [
            "tavily", "finnhub", "exa", "firecrawl", "reddit",
            "akshare", "openai", "anthropic", "langchain",
        ]
        violations = [i for i in imports if any(kw in i.lower() for kw in provider_keywords)]
        assert not violations, f"host_subprocess_runner imports provider SDKs: {violations}"

    def test_does_not_import_network_clients(self):
        source = _read_runner()
        imports = _get_imports(source)
        network_keywords = ["requests", "httpx", "aiohttp", "urllib3", "socket"]
        violations = [i for i in imports if any(kw in i.lower() for kw in network_keywords)]
        assert not violations, f"host_subprocess_runner imports network clients: {violations}"


class TestHostRunnerNoBrokerOrder:
    def test_does_not_claim_broker_order_execution(self):
        source = _read_runner()
        forbidden = ["broker_order", "place_order", "execute_trade", "order_execution"]
        for token in forbidden:
            assert token not in source, f"host_subprocess_runner claims {token}"


class TestHostRunnerDocstring:
    def test_docstring_mentions_host_owns_data_fetching(self):
        source = _read_runner()
        assert "host owns data fetching" in source.lower() or "Host owns data fetching" in source

    def test_docstring_mentions_fake_sample_fixtures(self):
        source = _read_runner()
        lower = source.lower()
        assert "fake" in lower or "sample" in lower

    def test_docstring_mentions_no_broker_order(self):
        source = _read_runner()
        lower = source.lower()
        assert "no broker" in lower or "no order execution" in lower


class TestHostRunnerFunctional:
    @pytest.fixture(autouse=True)
    def _import_runner(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("host_subprocess_runner", str(RUNNER_PATH))
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._mod = mod

    def test_run_json_skill_fund_analysis(self):
        result = self._mod.run_json_skill(
            "fund_analysis",
            ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json",
            repo_root=ROOT,
        )
        assert result.get("ok") is True
        assert result.get("skill_name") == "fund_analysis"

    def test_run_json_skill_decision_support(self):
        result = self._mod.run_json_skill(
            "decision_support",
            ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json",
            repo_root=ROOT,
        )
        assert result.get("ok") is True
        assert result.get("skill_name") == "decision_support"

    def test_run_json_skill_thesis_generation(self):
        result = self._mod.run_json_skill(
            "thesis_generation",
            ROOT / "examples" / "thesis_generation" / "evidence_graph_balanced_thesis.json",
            repo_root=ROOT,
        )
        assert result.get("ok") is True
        assert result.get("skill_name") == "thesis_generation"

    def test_run_markdown_report_returns_markdown(self):
        md = self._mod.run_markdown_report(
            ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json",
            repo_root=ROOT,
        )
        assert "# " in md or "## " in md
        with pytest.raises(json.JSONDecodeError):
            json.loads(md)
