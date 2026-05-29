# DEPRECATED — use src.graph.industry_map instead.
import warnings
warnings.warn(
    "src.kg.industry_map is deprecated, use src.graph.industry_map instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.graph.industry_map import *  # noqa: F401, F403
