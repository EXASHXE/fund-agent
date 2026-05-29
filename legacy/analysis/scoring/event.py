"""Compatibility entrypoint for EventScore.

The implementation lives in `event_score.py`; this module keeps the plan-named
`src.analysis.scoring.event` import path available.
"""
from legacy.analysis.scoring.event_score import EventScoreCalculator

__all__ = ["EventScoreCalculator"]
