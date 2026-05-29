"""Tests for Critic and CritiqueResult — structural evidence review."""

from __future__ import annotations

from datetime import datetime

import pytest
from src.core.critic import Critic, CritiqueResult, CritiqueStatus
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def empty_graph():
    """Empty EvidenceGraph with no items."""
    return EvidenceGraph()


@pytest.fixture
def hard_evidence_only():
    """Graph with a single HardEvidence item (traceable, no risk keywords)."""
    g = EvidenceGraph()
    item = EvidenceItem.from_tool_output(
        tool_name="quant_tool",
        output={"momentum": 0.8},
        claim="Momentum signal is positive",
        entities=["fund:110011"],
        direction="positive",
        provenance={"source": "quant_tool"},
    )
    g.add(item)
    return g


@pytest.fixture
def soft_evidence_only():
    """Graph with a single SoftEvidence item from one source."""
    g = EvidenceGraph()
    item = EvidenceItem.from_news(
        source="finnhub",
        news_item={"title": "Market sentiment is positive", "claim": "Market sentiment is positive"},
        entities=["fund:110011"],
        direction="positive",
        confidence=0.6,
    )
    g.add(item)
    return g


@pytest.fixture
def conflicting_evidence():
    """Graph with two items having opposite directions on the same entity."""
    g = EvidenceGraph()
    item1 = EvidenceItem.from_tool_output(
        tool_name="quant_tool",
        output={},
        claim="Positive outlook",
        entities=["fund:110011"],
        direction="positive",
        provenance={"source": "quant_tool"},
    )
    item2 = EvidenceItem.from_news(
        source="news_source",
        news_item={"title": "Negative outlook", "claim": "Negative outlook"},
        entities=["fund:110011"],
        direction="negative",
        confidence=0.5,
    )
    g.add(item1)
    g.add(item2)
    return g


@pytest.fixture
def mixed_evidence_graph():
    """Graph with both HardEvidence and SoftEvidence from multiple sources."""
    g = EvidenceGraph()
    g.add(EvidenceItem.from_tool_output(
        tool_name="quant_tool",
        output={"sharpe": 1.5},
        claim="Sharpe ratio is 1.5 indicating good risk-adjusted return",
        entities=["fund:110011"],
        direction="positive",
        provenance={"source": "quant_tool"},
    ))
    g.add(EvidenceItem.from_news(
        source="finnhub",
        news_item={"title": "Analyst upgrades fund", "claim": "Analyst upgrades fund"},
        entities=["fund:110011"],
        direction="positive",
        confidence=0.7,
    ))
    g.add(EvidenceItem.from_news(
        source="tavily",
        news_item={"title": "Sector rotation favors holdings", "claim": "Sector rotation favors holdings"},
        entities=["fund:110011"],
        direction="positive",
        confidence=0.65,
    ))
    return g


@pytest.fixture
def risk_evidence_graph():
    """Graph with risk-related evidence."""
    g = EvidenceGraph()
    item = EvidenceItem.from_tool_output(
        tool_name="risk_tool",
        output={"volatility": 0.15, "sharpe": 1.2},
        claim="Volatility and Sharpe ratio within acceptable range",
        entities=["fund:110011"],
        direction="neutral",
        provenance={"source": "risk_tool"},
    )
    g.add(item)
    return g


@pytest.fixture
def untraceable_graph():
    """Graph with an item that has no provenance."""
    g = EvidenceGraph()
    # Construct item without provenance
    item = EvidenceItem(
        evidence_id="no-prov",
        evidence_type="SoftEvidence",
        source_type="unknown",
        timestamp=datetime.now(),
        related_entities=["fund:110011"],
        claim="Some claim without source tracking",
        value={"data": "opaque"},
        confidence_weight=0.5,
        direction="neutral",
        provenance={},
    )
    g.add(item)
    return g


@pytest.fixture
def dummy_task():
    """A simple dict-like task for tests that need one."""
    return {"task_id": "test-001", "objective": "evaluate fund performance"}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCriticHardEvidence:
    """Tests for HardEvidence coverage checks."""

    def test_critic_pass_empty_graph(self, empty_graph, dummy_task):
        """Empty graph returns missing-all for HardEvidence."""
        critic = Critic()
        result = critic.review(dummy_task, empty_graph)
        assert result.status in ("RETRY", "FAIL")
        assert "all" in result.missing_evidence

    def test_critic_hard_evidence_present(self, hard_evidence_only):
        """HardEvidence present → no HardEvidence missing flag."""
        critic = Critic()
        missing = critic._check_hard_evidence(hard_evidence_only)
        assert missing == []

    def test_critic_hard_evidence_count_zero_when_empty(self, empty_graph):
        """_check_hard_evidence returns ["all"] when graph has no items."""
        critic = Critic()
        missing = critic._check_hard_evidence(empty_graph)
        assert missing == ["all"]


class TestCriticSoftEvidenceBias:
    """Tests for single-source SoftEvidence bias detection."""

    def test_critic_single_source_soft(self, soft_evidence_only):
        """Only SoftEvidence from one source → flag as single-source."""
        critic = Critic()
        biased = critic._check_single_source_bias(soft_evidence_only)
        assert len(biased) == 1
        assert "fund:110011" in biased

    def test_critic_multi_source_soft_not_biased(self, mixed_evidence_graph):
        """SoftEvidence from multiple sources → no bias flag."""
        critic = Critic()
        biased = critic._check_single_source_bias(mixed_evidence_graph)
        assert biased == []

    def test_critic_no_bias_with_only_hard_evidence(self, hard_evidence_only):
        """Only HardEvidence → no single-source SoftEvidence bias."""
        critic = Critic()
        biased = critic._check_single_source_bias(hard_evidence_only)
        assert biased == []


class TestCriticContradictions:
    """Tests for conflict/contradiction detection."""

    def test_critic_detect_contradictions(self, conflicting_evidence):
        """Opposite directions on same entity → detects conflict."""
        critic = Critic()
        contradictions = critic._check_contradictions(conflicting_evidence)
        assert len(contradictions) == 1
        assert "vs" in contradictions[0]

    def test_critic_no_contradictions_in_uniform_graph(self, hard_evidence_only):
        """Single-direction evidence → no contradictions."""
        critic = Critic()
        contradictions = critic._check_contradictions(hard_evidence_only)
        assert contradictions == []

    def test_critic_empty_graph_no_contradictions(self, empty_graph):
        """Empty graph → no contradictions."""
        critic = Critic()
        contradictions = critic._check_contradictions(empty_graph)
        assert contradictions == []


class TestCriticCircuitBreaker:
    """Tests for the iteration-based circuit breaker."""

    def test_critic_iteration_limit(self, hard_evidence_only, dummy_task):
        """iteration >= 3 → circuit breaker forces PASS."""
        critic = Critic()
        result = critic.review(dummy_task, hard_evidence_only, iteration=3)
        assert result.status == "PASS"
        assert any("circuit breaker" in issue.lower() for issue in result.issues)

    def test_critic_iteration_limit_exact_max(self, hard_evidence_only, dummy_task):
        """iteration == MAX_ITERATIONS → circuit breaker triggers."""
        critic = Critic()
        result = critic.review(dummy_task, hard_evidence_only, iteration=critic.MAX_ITERATIONS)
        assert result.status == "PASS"

    def test_critic_iteration_below_limit_no_breaker(self, mixed_evidence_graph, dummy_task):
        """iteration < 3 → circuit breaker does NOT trigger prematurely."""
        critic = Critic()
        result = critic.review(dummy_task, mixed_evidence_graph, iteration=1)
        # mixed_evidence_graph has hard + multi-source soft, should PASS on its own
        assert result.status == "PASS"
        assert not any("circuit breaker" in issue.lower() for issue in result.issues)


class TestCriticRiskEvidence:
    """Tests for missing risk evidence detection."""

    def test_critic_missing_risk_evidence(self, hard_evidence_only):
        """No risk-related evidence → flag as missing_risk."""
        critic = Critic()
        missing = critic._check_missing_risk_evidence(hard_evidence_only)
        assert "risk_metrics" in missing

    def test_critic_risk_evidence_present(self, risk_evidence_graph):
        """Risk evidence present → no missing flag."""
        critic = Critic()
        missing = critic._check_missing_risk_evidence(risk_evidence_graph)
        assert missing == []

    def test_critic_empty_graph_missing_risk(self, empty_graph):
        """Empty graph → risk_metrics missing."""
        critic = Critic()
        missing = critic._check_missing_risk_evidence(empty_graph)
        assert "risk_metrics" in missing


class TestCriticUntraceable:
    """Tests for untraceable evidence nodes."""

    def test_critic_untraceable_nodes(self, untraceable_graph):
        """Empty provenance → flag as untraceable."""
        critic = Critic()
        untraceable = critic._check_untraceable_nodes(untraceable_graph)
        assert len(untraceable) == 1
        assert "no-prov" in untraceable

    def test_critic_traceable_nodes_pass(self, hard_evidence_only):
        """Evidence with provenance → no untraceable flag."""
        critic = Critic()
        untraceable = critic._check_untraceable_nodes(hard_evidence_only)
        assert untraceable == []

    def test_critic_untraceable_causes_fail(self, untraceable_graph, dummy_task):
        """Untraceable nodes → review returns FAIL status."""
        critic = Critic()
        result = critic.review(dummy_task, untraceable_graph, iteration=0)
        assert result.status == "FAIL"
        assert any("untraceable" in str(issue).lower() for issue in result.issues)


class TestCriticInferenceLeaps:
    """Tests for inference leap detection (SoftEvidence without HardEvidence)."""

    def test_critic_inference_leap_soft_only(self, soft_evidence_only):
        """SoftEvidence without HardEvidence → inference leap detected."""
        critic = Critic()
        leaps = critic._check_inference_leaps(soft_evidence_only)
        assert len(leaps) > 0
        assert "SoftEvidence without HardEvidence support" in leaps

    def test_critic_no_inference_leap_with_hard(self, mixed_evidence_graph):
        """Both Hard and Soft evidence → no inference leap."""
        critic = Critic()
        leaps = critic._check_inference_leaps(mixed_evidence_graph)
        assert leaps == []

    def test_critic_empty_graph_no_inference_leap(self, empty_graph):
        """Empty graph → no inference leap (nothing to contrast)."""
        critic = Critic()
        leaps = critic._check_inference_leaps(empty_graph)
        assert leaps == []


class TestCritiqueResult:
    """Tests for CritiqueResult dataclass properties."""

    def test_critic_status_is_pass_retry_or_fail(self, hard_evidence_only, dummy_task):
        """Review status is a valid CritiqueStatus value."""
        critic = Critic()
        result = critic.review(dummy_task, hard_evidence_only, iteration=0)
        assert result.status in ("PASS", "RETRY", "FAIL")

    def test_critic_critique_result_to_dict(self):
        """to_dict() serializes all fields correctly."""
        from datetime import datetime

        result = CritiqueResult(
            status="PASS",
            issues=["issue 1"],
            missing_evidence=["risk_metrics"],
            retry_plan_suggestions=["gather more data"],
            iteration=2,
        )
        d = result.to_dict()
        assert d["status"] == "PASS"
        assert d["issues"] == ["issue 1"]
        assert d["missing_evidence"] == ["risk_metrics"]
        assert d["retry_plan_suggestions"] == ["gather more data"]
        assert d["iteration"] == 2
        assert "reviewed_at" in d

    def test_critic_structured_output(self, hard_evidence_only, dummy_task):
        """Review result has issues, missing_evidence, and retry_suggestions fields."""
        critic = Critic()
        result = critic.review(dummy_task, hard_evidence_only, iteration=0)
        assert hasattr(result, "issues")
        assert hasattr(result, "missing_evidence")
        assert hasattr(result, "retry_plan_suggestions")
        assert isinstance(result.issues, list)
        assert isinstance(result.missing_evidence, list)
        assert isinstance(result.retry_plan_suggestions, list)

    def test_critic_default_fields(self):
        """CritiqueResult default fields are sensible."""
        result = CritiqueResult(status="PASS")
        assert result.issues == []
        assert result.missing_evidence == []
        assert result.retry_plan_suggestions == []
        assert result.iteration == 0

    def test_critic_full_review_pass(self, mixed_evidence_graph, dummy_task):
        """A well-formed evidence graph with HardEvidence + multi-source SoftEvidence → PASS."""
        critic = Critic()
        result = critic.review(dummy_task, mixed_evidence_graph, iteration=0)
        assert result.status == "PASS"
        assert result.issues == []

    def test_critic_full_review_retry(self, soft_evidence_only, dummy_task):
        """SoftEvidence-only graph → RETRY due to missing HardEvidence."""
        critic = Critic()
        result = critic.review(dummy_task, soft_evidence_only, iteration=0)
        assert result.status == "RETRY"
        assert len(result.retry_plan_suggestions) > 0
