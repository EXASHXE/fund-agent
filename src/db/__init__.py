"""DEPRECATED: use src.infra.persistence."""
import warnings
warnings.warn(
    "src.db is deprecated, use src.infra.persistence instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.persistence import *  # noqa: F401, F403
