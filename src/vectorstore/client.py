# DEPRECATED — use src.infra.vectorstore.client instead.
import warnings
warnings.warn(
    "src.vectorstore.client is deprecated, use src.infra.vectorstore.client instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore.client import *  # noqa: F401, F403
