# DEPRECATED — use src.graph.enrichment instead.
import warnings
warnings.warn(
    "src.kg.enrichment is deprecated, use src.graph.enrichment instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.graph.enrichment import *  # noqa: F401, F403
