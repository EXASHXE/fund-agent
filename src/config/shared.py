# DEPRECATED — use src.infra.config.shared instead.
import warnings
warnings.warn(
    "src.config.shared is deprecated, use src.infra.config.shared instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config.shared import *  # noqa: F401, F403
