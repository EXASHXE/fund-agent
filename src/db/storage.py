# DEPRECATED — use src.infra.persistence.storage instead.
import warnings
warnings.warn(
    "src.db.storage is deprecated, use src.infra.persistence.storage instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.persistence.storage import *  # noqa: F401, F403
