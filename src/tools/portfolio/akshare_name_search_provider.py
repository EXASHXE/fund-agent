"""AkShare-based fund identity name search provider — M7.12, M7.16.

Lazy-imports akshare at call time. Core never imports this module directly.
Must be injected by the pipeline layer (personal-run / e2e).

M7.16 rewrite: replaces fuzzy character-overlap search with exact-first
fund universe reverse lookup strategy.

Search order:
A. exact_full_name → unique match → candidate with match_bucket=exact
B. exact_name_without_punctuation → unique match → candidate with match_bucket=exact
C. same_core_name_and_share_class → unique match → candidate with match_bucket=exact
D. signature-compatible candidates (substring containment)
E. fuzzy fallback candidates (LCS-based similarity)

A/B/C unique hits → provider_verified eligible.
D/E candidates → never auto-verified.

Key rules:
- Never imported by core (src/tools/portfolio/) modules
- akshare import happens inside search_by_name, not at module level
- On import failure / network error: returns empty list with diagnostic
- On success: returns FundIdentityCandidate list sorted by relevance
- All candidates sorted by match_score descending, not DataFrame order
"""
from __future__ import annotations

from typing import Any

from src.tools.portfolio.fund_identity_candidate_discovery import (
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_LOW,
    BUCKET_MEDIUM,
    FundIdentityCandidate,
    FundIdentitySearchProvider,
    normalize_fund_name_for_search,
)
from src.tools.portfolio.fund_universe_identity_lookup import (
    EXACT_MATCH,
    FundUniverseEntry,
    FundUniverseIndex,
    build_fund_universe_index,
)
from src.tools.portfolio.provider_identity_cross_check import compute_name_similarity


# ── Exact match reason constants (M7.16) ────────────────────────────────

EXACT_FUND_UNIVERSE_NAME_MATCH = "exact_fund_universe_name_match"
EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH = "exact_fund_universe_name_without_punctuation_match"
EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH = "exact_core_name_and_share_class_match"


class AkShareNameSearchProvider:
    """Fund identity search provider backed by akshare fund_name_em.

    Implements FundIdentitySearchProvider protocol.
    akshare is lazy-imported on first search_by_name call.

    M7.16: Uses FundUniverseIndex for exact-first lookup instead of
    fuzzy character-overlap search.

    Diagnostics:
    - _last_error: str — last error message (empty if healthy)
    - _provider_status: str — "available" | "import_failed" | "network_error" | "unknown_error"
    - _search_count: int — number of search_by_name calls
    - _result_count: int — total candidates returned
    """

    def __init__(self) -> None:
        self._akshare: Any = None
        self._fund_name_df: Any = None  # Cached DataFrame
        self._universe_index: FundUniverseIndex | None = None
        self._last_error: str = ""
        self._provider_status: str = "available"
        self._search_count: int = 0
        self._result_count: int = 0
        self._cache_loaded: bool = False
        # M7.16 diagnostics
        self._exact_full_name_match_count: int = 0
        self._exact_without_punctuation_match_count: int = 0
        self._core_share_class_match_count: int = 0
        self._fuzzy_fallback_count: int = 0
        self._last_search_strategy: str = ""

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
        """Load the full fund name list from akshare and build universe index.

        Returns True if cache loaded successfully, False otherwise.
        """
        if self._cache_loaded:
            return self._universe_index is not None

        ak = self._ensure_akshare()
        if ak is None:
            return False

        try:
            df = ak.fund_name_em()
            self._fund_name_df = df
            self._cache_loaded = True

            # Build universe index from DataFrame
            self._build_universe_index(df)
            return True
        except Exception as exc:
            self._provider_status = "network_error"
            self._last_error = f"akshare fund_name_em failed: {type(exc).__name__}: {exc}"
            self._cache_loaded = True  # Don't retry
            return False

    def _build_universe_index(self, df: Any) -> None:
        """Build FundUniverseIndex from akshare DataFrame."""
        code_col = None
        name_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if "代码" in str(col) or "code" in col_lower:
                code_col = col
            if "简称" in str(col) or "名称" in str(col) or "name" in col_lower:
                name_col = col

        if code_col is None or name_col is None:
            if len(df.columns) >= 2:
                code_col = df.columns[0]
                name_col = df.columns[1]
            else:
                self._last_error = f"unexpected DataFrame columns: {list(df.columns)}"
                return

        entries = []
        for _, row in df.iterrows():
            fund_code = str(row[code_col]).strip()
            fund_name = str(row[name_col]).strip()
            if fund_code and fund_name:
                entries.append({"fund_code": fund_code, "fund_name": fund_name})

        self._universe_index = build_fund_universe_index(entries)

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search for fund codes matching a normalized name.

        M7.16: Uses exact-first lookup strategy:
        A. exact_full_name → unique match
        B. exact_name_without_punctuation → unique match
        C. same_core_name_and_share_class → unique match
        D. signature-compatible candidates
        E. fuzzy fallback candidates

        Returns candidates sorted by relevance (best first).
        On failure: returns empty list (diagnostic in _last_error).
        """
        self._search_count += 1

        if not normalized_name:
            return []

        if not self._load_fund_name_cache():
            return []

        if self._universe_index is None:
            return []

        try:
            return self._search_exact_first(normalized_name)
        except Exception as exc:
            self._provider_status = "unknown_error"
            self._last_error = f"search failed: {type(exc).__name__}: {exc}"
            return []

    def _search_exact_first(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Exact-first search strategy using FundUniverseIndex."""
        query_norm = normalize_fund_name_for_search(normalized_name)
        if not query_norm:
            return []

        candidates: list[FundIdentityCandidate] = []

        # ── Level A: exact full name ──────────────────────────────────
        result_a = self._universe_index.lookup_exact_full_name(query_norm)
        if result_a.lookup_status == EXACT_MATCH:
            entry = result_a.matched_entries[0]
            cand = self._make_exact_candidate(
                entry, EXACT_FUND_UNIVERSE_NAME_MATCH, 1.0,
            )
            candidates.append(cand)
            self._exact_full_name_match_count += 1
            self._last_search_strategy = "exact_full_name"
            self._result_count += len(candidates)
            return candidates

        # ── Level B: exact without punctuation ────────────────────────
        result_b = self._universe_index.lookup_exact_name_without_punctuation(query_norm)
        if result_b.lookup_status == EXACT_MATCH:
            entry = result_b.matched_entries[0]
            cand = self._make_exact_candidate(
                entry, EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH, 0.98,
            )
            candidates.append(cand)
            self._exact_without_punctuation_match_count += 1
            self._last_search_strategy = "exact_name_without_punctuation"
            # Also add ambiguous matches from level A if any
            if result_a.matched_entries:
                for entry in result_a.matched_entries:
                    c = self._make_exact_candidate(
                        entry, EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH, 0.95,
                    )
                    c.match_bucket = BUCKET_HIGH
                    candidates.append(c)
            self._result_count += len(candidates)
            candidates.sort(key=lambda c: c.match_score, reverse=True)
            return candidates

        # ── Level C: core name + share class ──────────────────────────
        result_c = self._universe_index.lookup_same_core_name_and_share_class(query_norm)
        if result_c.lookup_status == EXACT_MATCH:
            entry = result_c.matched_entries[0]
            cand = self._make_exact_candidate(
                entry, EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH, 0.96,
            )
            candidates.append(cand)
            self._core_share_class_match_count += 1
            self._last_search_strategy = "exact_core_name_and_share_class"
            # Also add level B ambiguous matches if any
            if result_b.matched_entries:
                for entry in result_b.matched_entries:
                    c = self._make_exact_candidate(
                        entry, EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH, 0.92,
                    )
                    c.match_bucket = BUCKET_HIGH
                    candidates.append(c)
            self._result_count += len(candidates)
            candidates.sort(key=lambda c: c.match_score, reverse=True)
            return candidates

        # ── Level D/E: signature and fuzzy fallback ──────────────────
        self._last_search_strategy = "fuzzy_fallback"
        self._fuzzy_fallback_count += 1
        fallback_candidates = self._fuzzy_search(query_norm)

        # Add any exact ambiguous matches from levels A/B/C as well
        for entry in result_a.matched_entries:
            c = self._make_fuzzy_candidate(entry, query_norm, "exact_full_name_ambiguous")
            if c.match_score > 0:
                fallback_candidates.append(c)
        for entry in result_b.matched_entries:
            c = self._make_fuzzy_candidate(entry, query_norm, "exact_no_punct_ambiguous")
            if c.match_score > 0:
                fallback_candidates.append(c)
        for entry in result_c.matched_entries:
            c = self._make_fuzzy_candidate(entry, query_norm, "core_share_class_ambiguous")
            if c.match_score > 0:
                fallback_candidates.append(c)

        # Sort by score descending (deterministic, not DataFrame order)
        fallback_candidates.sort(key=lambda c: c.match_score, reverse=True)

        self._result_count += len(fallback_candidates)
        return fallback_candidates

    def _make_exact_candidate(
        self,
        entry: FundUniverseEntry,
        match_reason: str,
        score: float,
    ) -> FundIdentityCandidate:
        """Create a candidate from an exact universe match."""
        return FundIdentityCandidate(
            fund_code=entry.fund_code,
            fund_name=entry.fund_name,
            source="akshare_fund_universe_exact",
            match_score=score,
            match_bucket=BUCKET_EXACT,
            match_reasons=[match_reason],
            risk_flags=[],
        )

    def _make_fuzzy_candidate(
        self,
        entry: FundUniverseEntry,
        query_norm: str,
        strategy_label: str,
    ) -> FundIdentityCandidate:
        """Create a candidate from a fuzzy/sig match with computed score."""
        cand = FundIdentityCandidate(
            fund_code=entry.fund_code,
            fund_name=entry.fund_name,
            source="akshare_fund_name_em",
        )
        # Compute similarity
        name_norm = normalize_fund_name_for_search(entry.fund_name)
        sim = compute_name_similarity(query_norm, name_norm)

        cand.match_score = round(sim, 4)
        cand.match_reasons = [strategy_label]

        if sim >= 0.95:
            cand.match_bucket = BUCKET_HIGH
        elif sim >= 0.85:
            cand.match_bucket = BUCKET_MEDIUM
        elif sim >= 0.70:
            cand.match_bucket = BUCKET_LOW
        else:
            cand.match_bucket = BUCKET_LOW
            cand.match_score = max(round(sim, 4), 0.0)

        return cand

    def _fuzzy_search(self, query_norm: str) -> list[FundIdentityCandidate]:
        """Fallback fuzzy search over the full universe index.

        Unlike the old approach, this searches ALL entries in the index,
        not just the first 50 from DataFrame iteration order.
        """
        if self._universe_index is None:
            return []

        candidates: list[FundIdentityCandidate] = []
        query_lower = query_norm.lower()

        for entry in self._universe_index._entries:
            name_norm = normalize_fund_name_for_search(entry.fund_name).lower()
            if not name_norm:
                continue

            # Quick filter: character overlap
            query_chars = set(query_lower)
            name_chars = set(name_norm)
            overlap = query_chars & name_chars
            if len(overlap) < max(2, len(query_chars) * 0.3):
                continue

            # Substring check
            has_substring = query_lower in name_norm or name_norm in query_lower

            # Compute similarity
            if not has_substring and len(overlap) < len(query_chars) * 0.5:
                continue

            cand = self._make_fuzzy_candidate(entry, query_norm, "fuzzy_fallback")
            if cand.match_score > 0:
                candidates.append(cand)

        return candidates

    def get_diagnostics(self) -> dict[str, Any]:
        """Return provider diagnostics (for run_manifest / agent_context)."""
        diag = {
            "name_search_provider_type": "akshare",
            "name_search_provider_status": self._provider_status,
            "name_search_provider_last_error": self._last_error,
            "name_search_provider_search_count": self._search_count,
            "name_search_provider_result_count": self._result_count,
            "name_search_provider_cache_loaded": self._cache_loaded,
        }
        # M7.16: Universe index diagnostics
        if self._universe_index is not None:
            diag["fund_universe_size"] = self._universe_index.size
        diag["exact_full_name_match_count"] = self._exact_full_name_match_count
        diag["exact_without_punctuation_match_count"] = self._exact_without_punctuation_match_count
        diag["core_share_class_match_count"] = self._core_share_class_match_count
        diag["fuzzy_fallback_count"] = self._fuzzy_fallback_count
        diag["search_strategy_used"] = self._last_search_strategy
        return diag
