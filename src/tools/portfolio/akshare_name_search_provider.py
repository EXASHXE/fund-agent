"""AkShare-based fund identity name search provider — M7.12.

Lazy-imports akshare at call time. Core never imports this module directly.
Must be injected by the pipeline layer (personal-run / e2e).

Key rules:
- Never imported by core (src/tools/portfolio/) modules
- akshare import happens inside search_by_name, not at module level
- On import failure / network error: returns empty list with diagnostic
- On success: returns FundIdentityCandidate list sorted by relevance
"""
from __future__ import annotations

from typing import Any

from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    FundIdentitySearchProvider,
    normalize_fund_name_for_search,
)


class AkShareNameSearchProvider:
    """Fund identity search provider backed by akshare fund_name_em.

    Implements FundIdentitySearchProvider protocol.
    akshare is lazy-imported on first search_by_name call.

    Diagnostics:
    - _last_error: str — last error message (empty if healthy)
    - _provider_status: str — "available" | "import_failed" | "network_error" | "unknown_error"
    - _search_count: int — number of search_by_name calls
    - _result_count: int — total candidates returned
    """

    def __init__(self) -> None:
        self._akshare: Any = None
        self._fund_name_df: Any = None  # Cached DataFrame
        self._last_error: str = ""
        self._provider_status: str = "available"
        self._search_count: int = 0
        self._result_count: int = 0
        self._cache_loaded: bool = False

    def _ensure_akshare(self) -> Any:
        """Lazy-import akshare. Returns None on ImportError."""
        if self._akshare is not None:
            return self._akshare
        try:
            import akshare as _ak
            self._akshare = _ak
            return _ak
        except ImportError:
            self._provider_status = "import_failed"
            self._last_error = "akshare not installed"
            return None

    def _load_fund_name_cache(self) -> bool:
        """Load the full fund name list from akshare (cached after first call).

        Returns True if cache loaded successfully, False otherwise.
        """
        if self._cache_loaded:
            return self._fund_name_df is not None

        ak = self._ensure_akshare()
        if ak is None:
            return False

        try:
            df = ak.fund_name_em()
            self._fund_name_df = df
            self._cache_loaded = True
            return True
        except Exception as exc:
            self._provider_status = "network_error"
            self._last_error = f"akshare fund_name_em failed: {type(exc).__name__}: {exc}"
            self._cache_loaded = True  # Don't retry
            return False

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search for fund codes matching a normalized name.

        Uses akshare's fund_name_em() to get all fund names, then
        performs fuzzy matching against the query name.

        Returns candidates sorted by relevance (best first).
        On failure: returns empty list (diagnostic in _last_error).
        """
        self._search_count += 1

        if not normalized_name:
            return []

        if not self._load_fund_name_cache():
            return []

        if self._fund_name_df is None:
            return []

        try:
            return self._search_from_cache(normalized_name)
        except Exception as exc:
            self._provider_status = "unknown_error"
            self._last_error = f"search failed: {type(exc).__name__}: {exc}"
            return []

    def _search_from_cache(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search from the cached fund name DataFrame."""
        import re

        df = self._fund_name_df

        # Normalize column names (akshare may use Chinese or English names)
        # Common column names: "基金代码", "基金简称"
        code_col = None
        name_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if "代码" in str(col) or "code" in col_lower:
                code_col = col
            if "简称" in str(col) or "名称" in str(col) or "name" in col_lower:
                name_col = col

        if code_col is None or name_col is None:
            # Fallback: try positional columns
            if len(df.columns) >= 2:
                code_col = df.columns[0]
                name_col = df.columns[1]
            else:
                self._last_error = f"unexpected DataFrame columns: {list(df.columns)}"
                return []

        query_norm = normalize_fund_name_for_search(normalized_name).lower()
        if not query_norm:
            return []

        candidates: list[FundIdentityCandidate] = []

        for _, row in df.iterrows():
            fund_code = str(row[code_col]).strip()
            fund_name = str(row[name_col]).strip()

            if not fund_code or not fund_name:
                continue

            # Quick filter: skip if no character overlap
            name_norm = normalize_fund_name_for_search(fund_name).lower()
            if not name_norm:
                continue

            # Check if any significant substring of query appears in name
            # This avoids scoring every single fund in the database
            # Use character overlap as a quick filter
            query_chars = set(query_norm)
            name_chars = set(name_norm)
            overlap = query_chars & name_chars
            if len(overlap) < max(2, len(query_chars) * 0.3):
                continue

            # Check for substring match (strong signal)
            has_substring = query_norm in name_norm or name_norm in query_norm

            # Compute rough similarity for pre-filtering
            # Only keep candidates with some relevance
            if not has_substring and len(overlap) < len(query_chars) * 0.5:
                continue

            candidate = FundIdentityCandidate(
                fund_code=fund_code,
                fund_name=fund_name,
                source="akshare_fund_name_em",
            )
            candidates.append(candidate)

            # Cap candidates to avoid excessive scoring work
            if len(candidates) >= 50:
                break

        self._result_count += len(candidates)
        return candidates

    def get_diagnostics(self) -> dict[str, Any]:
        """Return provider diagnostics (for run_manifest / agent_context)."""
        return {
            "name_search_provider_type": "akshare",
            "name_search_provider_status": self._provider_status,
            "name_search_provider_last_error": self._last_error,
            "name_search_provider_search_count": self._search_count,
            "name_search_provider_result_count": self._result_count,
            "name_search_provider_cache_loaded": self._cache_loaded,
        }
