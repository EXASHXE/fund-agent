# DEPRECATED — use src.infra.config.loader instead.
import warnings
warnings.warn(
    "src.config.loader is deprecated, use src.infra.config.loader instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config.loader import *  # noqa: F401, F403
