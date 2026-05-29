# DEPRECATED — use src.infra.vectorstore.collections instead.
import warnings
warnings.warn(
    "src.vectorstore.collections is deprecated, use src.infra.vectorstore.collections instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore.collections import *  # noqa: F401, F403
