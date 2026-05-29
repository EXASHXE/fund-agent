# DEPRECATED — use src.graph.diff instead.
import warnings
warnings.warn(
    "src.kg.diff is deprecated, use src.graph.diff instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.graph.diff import *  # noqa: F401, F403
