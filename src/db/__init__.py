"""DEPRECATED — use src.infra.persistence instead."""
import warnings
warnings.warn(
    "src.db is deprecated, use src.infra.persistence instead",
    DeprecationWarning,
    stacklevel=2,
)
from src.infra.persistence.storage import FundStorage
from src.infra.persistence.database import get_session, init_db
from src.infra.persistence.models import Base, Fund

__all__ = ["FundStorage", "get_session", "init_db", "Base", "Fund"]
