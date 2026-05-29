# DEPRECATED — use src.infra.data.fetcher instead.
import warnings
warnings.warn(
    "src.data.fetcher is deprecated, use src.infra.data.fetcher instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.data.fetcher import *  # noqa: F401, F403
