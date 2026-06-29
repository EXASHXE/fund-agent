"""M7.13 Local identity candidate cache provider.

Reads a private, read-only cache file from private_data/ as a fallback
when network providers are unavailable. Cache candidates go through M7.11
deterministic scoring and auto-verify — they are NOT user_verified.

Cache file location:
  private_data/fund_identity_candidate_cache.private.csv
  private_data/fund_identity_candidate_cache.private.json

CSV fields:
  normalized_name, fund_code, fund_name, fund_type, share_class,
  source, updated_at, confidence_hint, notes

Rules:
1. Cache is read-only — pipeline never writes to it.
2. Cache candidate source = local_identity_candidate_cache.
3. Cache is NOT equivalent to user_verified.
4. Cache candidates enter M7.11 scoring pipeline.
5. If unique high-confidence and no risk flags: can auto provider_verified.
6. If ambiguous: stays unverified, enters identity_candidates.private.csv.
7. Cache file must be under private_data/ and covered by privacy check.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    FundIdentitySearchProvider,
    normalize_fund_name_for_search,
)


class LocalIdentityCandidateCacheProvider:
    """Fund identity search provider backed by a local private cache file.

    Implements FundIdentitySearchProvider protocol.
    Reads from CSV or JSON cache — never writes.
    Source is always "local_identity_candidate_cache".
    """

    _provider_name = "local_cache"

    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache_path = cache_path
        self._cache: dict[str, list[FundIdentityCandidate]] = {}
        self._cache_loaded: bool = False
        self._load_error: str = ""
        self._provider_status: str = "available"
        self._search_count: int = 0
        self._result_count: int = 0
        self._entry_count: int = 0

    def _load_cache(self) -> bool:
        """Load cache from file (CSV or JSON). Returns True if loaded."""
        if self._cache_loaded:
            return bool(self._cache)

        self._cache_loaded = True

        if self._cache_path is None or not self._cache_path.exists():
            self._provider_status = "cache_missing"
            self._load_error = "cache file not found"
            return False

        try:
            suffix = self._cache_path.suffix.lower()
            if suffix == ".json":
                self._load_json_cache()
            elif suffix == ".csv":
                self._load_csv_cache()
            else:
                self._provider_status = "cache_format_unsupported"
                self._load_error = f"unsupported cache format: {suffix}"
                return False

            if self._cache:
                self._provider_status = "available"
            else:
                self._provider_status = "cache_empty"
                self._load_error = "cache loaded but empty"
            return bool(self._cache)

        except Exception as exc:
            self._provider_status = "cache_load_error"
            self._load_error = f"failed to load cache: {type(exc).__name__}: {exc}"
            return False

    def _load_csv_cache(self) -> None:
        """Load cache from CSV file."""
        text = self._cache_path.read_text(encoding="utf-8")
        reader = csv.DictReader(text.splitlines())

        for row in reader:
            norm_name = normalize_fund_name_for_search(
                row.get("normalized_name", "").strip()
            )
            fund_code = row.get("fund_code", "").strip()
            fund_name = row.get("fund_name", "").strip()

            if not norm_name or not fund_code:
                continue

            candidate = FundIdentityCandidate(
                fund_code=fund_code,
                fund_name=fund_name,
                fund_type=row.get("fund_type", "").strip(),
                share_class=row.get("share_class", "").strip(),
                source="local_identity_candidate_cache",
            )

            self._cache.setdefault(norm_name, []).append(candidate)
            self._entry_count += 1

    def _load_json_cache(self) -> None:
        """Load cache from JSON file."""
        data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("entries", [])

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            norm_name = normalize_fund_name_for_search(
                entry.get("normalized_name", "").strip()
            )
            fund_code = entry.get("fund_code", "").strip()
            fund_name = entry.get("fund_name", "").strip()

            if not norm_name or not fund_code:
                continue

            candidate = FundIdentityCandidate(
                fund_code=fund_code,
                fund_name=fund_name,
                fund_type=entry.get("fund_type", "").strip(),
                share_class=entry.get("share_class", "").strip(),
                source="local_identity_candidate_cache",
            )

            self._cache.setdefault(norm_name, []).append(candidate)
            self._entry_count += 1

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search cache for candidates matching a normalized name.

        Returns candidates from cache or empty list.
        """
        self._search_count += 1

        if not normalized_name:
            return []

        if not self._load_cache():
            return []

        # Exact match on normalized_name
        candidates = self._cache.get(normalized_name, [])
        self._result_count += len(candidates)

        return list(candidates)  # Return copies

    def get_diagnostics(self) -> dict[str, Any]:
        """Return provider diagnostics (for run_manifest / agent_context)."""
        return {
            "name_search_provider_type": "local_cache",
            "name_search_provider_status": self._provider_status,
            "name_search_provider_last_error": self._load_error,
            "name_search_provider_search_count": self._search_count,
            "name_search_provider_result_count": self._result_count,
            "name_search_provider_cache_loaded": self._cache_loaded,
            "name_search_provider_cache_path": (
                str(self._cache_path.name) if self._cache_path else ""
            ),
            "name_search_provider_entry_count": self._entry_count,
        }
