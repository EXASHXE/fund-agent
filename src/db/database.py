# DEPRECATED — use src.infra.persistence.database instead.
import warnings
warnings.warn(
    "src.db.database is deprecated, use src.infra.persistence.database instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.persistence.database import *  # noqa: F401, F403
