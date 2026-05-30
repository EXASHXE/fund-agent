"""DEPRECATED: use src.infra.vectorstore."""
import warnings
warnings.warn(
    "src.vectorstore is deprecated, use src.infra.vectorstore instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.vectorstore import *  # noqa: F401, F403
