# DEPRECATED — use src.infra.vectorstore.search instead.
import warnings
warnings.warn(
    "src.vectorstore.search is deprecated, use src.infra.vectorstore.search instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore.search import *  # noqa: F401, F403
