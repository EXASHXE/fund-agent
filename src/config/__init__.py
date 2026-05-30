"""DEPRECATED: use src.infra.config."""
import warnings
warnings.warn(
    "src.config is deprecated, use src.infra.config instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.config import *  # noqa: F401, F403
