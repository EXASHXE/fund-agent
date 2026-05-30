"""DEPRECATED: use src.infra.data."""
import warnings
warnings.warn(
    "src.data is deprecated, use src.infra.data instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.data import *  # noqa: F401, F403
