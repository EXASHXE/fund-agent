"""Tests for architecture entrypoints named in the OS restructure plan."""


def test_scoring_event_module_exports_event_score_calculator():
    from legacy.analysis.scoring.event import EventScoreCalculator
    from legacy.analysis.scoring.event_score import EventScoreCalculator as Existing

    assert EventScoreCalculator is Existing


def test_agents_graph_module_exports_compiled_graph_builders():
    from legacy.agents.graph import build_research_graph, build_research_graph_with_routing
    from legacy.agents.state import EMPTY_STATE

    graph = build_research_graph()
    routed_graph = build_research_graph_with_routing()

    assert graph is not None
    assert routed_graph is not None
    assert isinstance(graph.invoke(dict(EMPTY_STATE)), dict)
