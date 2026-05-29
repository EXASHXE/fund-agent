# DEPRECATED — use src.graph.builder instead.
import warnings
warnings.warn(
    "src.kg.graph is deprecated, use src.graph.builder instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.graph.builder import *  # noqa: F401, F403

