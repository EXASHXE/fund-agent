# DEPRECATED — use src.infra.vectorstore.embedding instead.
import warnings
warnings.warn(
    "src.vectorstore.embedding is deprecated, use src.infra.vectorstore.embedding instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore.embedding import *  # noqa: F401, F403
