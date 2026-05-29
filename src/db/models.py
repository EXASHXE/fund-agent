# DEPRECATED — use src.infra.persistence.models instead.
import warnings
warnings.warn(
    "src.db.models is deprecated, use src.infra.persistence.models instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.persistence.models import *  # noqa: F401, F403
