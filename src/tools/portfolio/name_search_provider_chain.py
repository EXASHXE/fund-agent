"""M7.13 Provider fallback chain for fund identity name search.

Chains multiple FundIdentitySearchProvider instances. When a provider fails
(network error, SSL, timeout), the chain continues to the next provider.
Candidates from multiple providers are merged, deduplicated, and scored.

Key rules:
- A provider failure does NOT terminate the chain.
- All provider diagnostics are aggregated.
- Same fund_code from multiple sources gets a multi_source bonus but
  cannot bypass share_class/QDII/ETF risk checks.
- Provider failures are structurally recorded — never silently become name_only.
"""
from __future__ import annotations

from typing import Any

from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    FundIdentitySearchProvider,
    NullFundIdentitySearchProvider,
)


class ChainedFundIdentitySearchProvider:
    """Chain of FundIdentitySearchProvider instances with fallback.

    Providers are called in order. If a provider raises an exception or
    returns no results, the chain continues. Candidates from multiple
    providers are merged and deduplicated by fund_code.

    Diagnostics track which providers were attempted, succeeded, or failed.
    """

    def __init__(self, providers: list[FundIdentitySearchProvider]) -> None:
        self._providers: list[FundIdentitySearchProvider] = providers
        self._provider_names: list[str] = []
        for p in self._providers:
            name = getattr(p, "_provider_name", type(p).__name__)
            self._provider_names.append(name)

        # Diagnostics state — track unique provider outcomes (not per-search)
        self._search_count: int = 0
        self._result_count: int = 0
        self._providers_attempted_set: set[str] = set()
        self._providers_succeeded_set: set[str] = set()
        self._providers_failed_set: set[str] = set()
        self._provider_errors: dict[str, str] = {}
        self._fallback_used: bool = False
        self._candidate_sources: dict[str, list[str]] = {}

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search all providers in order, merge and deduplicate candidates.

        A provider failure (exception or empty result) does not stop the chain.
        """
        self._search_count += 1

        if not normalized_name:
            return []

        all_candidates: dict[str, FundIdentityCandidate] = {}
        candidate_sources: dict[str, list[str]] = {}
        first_provider_had_results = False

        for i, provider in enumerate(self._providers):
            p_name = self._provider_names[i]
            self._providers_attempted_set.add(p_name)

            try:
                raw_candidates = provider.search_by_name(normalized_name)
            except Exception as exc:
                self._providers_failed_set.add(p_name)
                self._provider_errors[p_name] = f"{type(exc).__name__}: {exc}"
                continue

            if raw_candidates:
                self._providers_succeeded_set.add(p_name)
                if not first_provider_had_results:
                    first_provider_had_results = True
                else:
                    self._fallback_used = True

                for cand in raw_candidates:
                    code = cand.fund_code
                    if code in all_candidates:
                        # Merge: keep existing, record multi-source
                        candidate_sources.setdefault(code, []).append(cand.source or p_name)
                    else:
                        all_candidates[code] = cand
                        candidate_sources[code] = [cand.source or p_name]
            else:
                # Provider returned empty — could be failure or no match
                # Check if provider has diagnostics indicating failure
                diag = {}
                if hasattr(provider, "get_diagnostics"):
                    diag = provider.get_diagnostics()
                status = diag.get("name_search_provider_status", "")
                if status in ("import_failed", "network_error", "unknown_error"):
                    self._providers_failed_set.add(p_name)
                    err = diag.get("name_search_provider_last_error", "unknown error")
                    self._provider_errors[p_name] = err
                else:
                    # Provider succeeded but found no matches
                    self._providers_succeeded_set.add(p_name)

        # Apply multi-source bonus to candidates from multiple providers
        for code, sources in candidate_sources.items():
            if len(sources) > 1 and code in all_candidates:
                cand = all_candidates[code]
                # Small bonus for multi-source confirmation, but cannot bypass risk checks
                cand.match_score = min(1.0, cand.match_score + 0.05)
                if "multi_source_confirmation" not in cand.match_reasons:
                    cand.match_reasons.append("multi_source_confirmation")

        self._candidate_sources = candidate_sources
        self._result_count += len(all_candidates)

        # Sort by match_score descending
        results = sorted(all_candidates.values(), key=lambda c: c.match_score, reverse=True)
        return results

    def get_diagnostics(self) -> dict[str, Any]:
        """Return chain diagnostics (for run_manifest / agent_context)."""
        return {
            "provider_chain_enabled": True,
            "providers_attempted": sorted(self._providers_attempted_set),
            "providers_succeeded": sorted(self._providers_succeeded_set),
            "providers_failed": sorted(self._providers_failed_set),
            "provider_errors_by_name": dict(self._provider_errors),
            "fallback_used": self._fallback_used,
            "candidate_sources": {k: v for k, v in self._candidate_sources.items()},
            "provider_chain_search_count": self._search_count,
            "provider_chain_result_count": self._result_count,
        }
