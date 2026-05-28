"""Factor analysis tools: factor matrix builder and score confidence calculator.

All classes in this package are PURE — they have zero IO, zero network,
zero LLM calls. They operate only on their input arguments.
"""

from src.tools.factors.builder import FactorMatrixBuilder

__all__ = [
    "FactorMatrixBuilder",
]
