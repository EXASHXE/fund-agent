# DEPRECATED — use src.infra.config.defaults instead.
import warnings
warnings.warn(
    "src.config.defaults is deprecated, use src.infra.config.defaults instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config.defaults import *  # noqa: F401, F403
