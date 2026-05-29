# DEPRECATED — use src.graph.schema instead.
import warnings
warnings.warn(
    "src.kg.schema is deprecated, use src.graph.schema instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.graph.schema import *  # noqa: F401, F403
