# DEPRECATED — use src.infra.config.schema instead.
import warnings
warnings.warn(
    "src.config.schema is deprecated, use src.infra.config.schema instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config.schema import *  # noqa: F401, F403
