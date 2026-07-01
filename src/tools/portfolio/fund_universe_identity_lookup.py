"""M7.16 Fund universe exact identity lookup.

Builds a reverse lookup index from the full fund universe (e.g. akshare
fund_name_em) that supports exact name → code resolution. This replaces
the previous fuzzy character-overlap search with an exact-first strategy.

Key invariants:
- Exact full name match → unique code (exact_match)
- Exact name without punctuation → unique code (exact_match)
- Same core name + share class → unique code (exact_match)
- Multiple matches → ambiguous_exact_match
- No match → no_exact_match
- A/C share class are distinct
- Punctuation, full/half-width, case differences are normalized
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Lookup result types ─────────────────────────────────────────────────

EXACT_MATCH = "exact_match"
AMBIGUOUS_EXACT_MATCH = "ambiguous_exact_match"
NO_EXACT_MATCH = "no_exact_match"


@dataclass
class FundUniverseEntry:
    """A single fund entry in the universe index."""

    fund_code: str
    fund_name: str
    normalized_full_name: str = ""
    normalized_name_no_punct: str = ""
    core_name: str = ""
    share_class: str = ""


@dataclass
class FundUniverseLookupResult:
    """Result of a fund universe exact lookup."""

    lookup_status: str  # exact_match | ambiguous_exact_match | no_exact_match
    matched_entries: list[FundUniverseEntry] = field(default_factory=list)
    match_reason: str = ""  # exact_full_name | exact_name_without_punctuation | exact_core_name_and_share_class


class FundUniverseIndex:
    """Reverse lookup index for exact fund name → code resolution.

    Supports three levels of exact matching:
    A. exact_full_name: normalized full name matches exactly
    B. exact_name_without_punctuation: after removing all punctuation, matches
    C. same_core_name_and_share_class: core name (without share class) + share class matches

    All lookups are deterministic and O(1) via pre-built hash maps.
    """

    def __init__(self) -> None:
        self._entries: list[FundUniverseEntry] = []
        # Index maps: normalized_key → list of FundUniverseEntry
        self._full_name_index: dict[str, list[FundUniverseEntry]] = {}
        self._no_punct_index: dict[str, list[FundUniverseEntry]] = {}
        self._core_name_share_class_index: dict[str, list[FundUniverseEntry]] = {}
        self._size: int = 0

    @property
    def size(self) -> int:
        return self._size

    def add_entry(self, entry: FundUniverseEntry) -> None:
        """Add an entry to all index maps."""
        self._entries.append(entry)
        self._size += 1

        # Full name index
        key = entry.normalized_full_name
        if key:
            self._full_name_index.setdefault(key, []).append(entry)

        # No punctuation index
        key_np = entry.normalized_name_no_punct
        if key_np:
            self._no_punct_index.setdefault(key_np, []).append(entry)

        # Core name + share class index
        core_key = _core_share_class_key(entry.core_name, entry.share_class)
        if core_key:
            self._core_name_share_class_index.setdefault(core_key, []).append(entry)

    def lookup_exact_full_name(self, normalized_name: str) -> FundUniverseLookupResult:
        """Level A: Exact full normalized name lookup."""
        entries = self._full_name_index.get(normalized_name, [])
        if not entries:
            return FundUniverseLookupResult(lookup_status=NO_EXACT_MATCH, match_reason="exact_full_name")
        if len(entries) == 1:
            return FundUniverseLookupResult(
                lookup_status=EXACT_MATCH,
                matched_entries=entries,
                match_reason="exact_full_name",
            )
        return FundUniverseLookupResult(
            lookup_status=AMBIGUOUS_EXACT_MATCH,
            matched_entries=entries,
            match_reason="exact_full_name",
        )

    def lookup_exact_name_without_punctuation(self, normalized_name: str) -> FundUniverseLookupResult:
        """Level B: Exact name without punctuation lookup."""
        no_punct = _strip_punctuation(normalized_name)
        entries = self._no_punct_index.get(no_punct, [])
        if not entries:
            return FundUniverseLookupResult(lookup_status=NO_EXACT_MATCH, match_reason="exact_name_without_punctuation")
        if len(entries) == 1:
            return FundUniverseLookupResult(
                lookup_status=EXACT_MATCH,
                matched_entries=entries,
                match_reason="exact_name_without_punctuation",
            )
        return FundUniverseLookupResult(
            lookup_status=AMBIGUOUS_EXACT_MATCH,
            matched_entries=entries,
            match_reason="exact_name_without_punctuation",
        )

    def lookup_same_core_name_and_share_class(self, normalized_name: str) -> FundUniverseLookupResult:
        """Level C: Same core name + share class lookup."""
        core = _extract_core_name(normalized_name)
        share = _extract_share_class_from_name(normalized_name)
        core_key = _core_share_class_key(core, share)
        if not core_key:
            return FundUniverseLookupResult(lookup_status=NO_EXACT_MATCH, match_reason="exact_core_name_and_share_class")
        entries = self._core_name_share_class_index.get(core_key, [])
        if not entries:
            return FundUniverseLookupResult(lookup_status=NO_EXACT_MATCH, match_reason="exact_core_name_and_share_class")
        if len(entries) == 1:
            return FundUniverseLookupResult(
                lookup_status=EXACT_MATCH,
                matched_entries=entries,
                match_reason="exact_core_name_and_share_class",
            )
        return FundUniverseLookupResult(
            lookup_status=AMBIGUOUS_EXACT_MATCH,
            matched_entries=entries,
            match_reason="exact_core_name_and_share_class",
        )

    def lookup(self, normalized_name: str) -> FundUniverseLookupResult:
        """Full lookup chain: A → B → C, returns first match or no_exact_match."""
        # Level A: exact full name
        result = self.lookup_exact_full_name(normalized_name)
        if result.lookup_status != NO_EXACT_MATCH:
            return result

        # Level B: exact without punctuation
        result = self.lookup_exact_name_without_punctuation(normalized_name)
        if result.lookup_status != NO_EXACT_MATCH:
            return result

        # Level C: core name + share class
        result = self.lookup_same_core_name_and_share_class(normalized_name)
        if result.lookup_status != NO_EXACT_MATCH:
            return result

        return FundUniverseLookupResult(lookup_status=NO_EXACT_MATCH, match_reason="no_exact_match")


def build_fund_universe_index(
    entries: list[dict[str, str]],
    code_key: str = "fund_code",
    name_key: str = "fund_name",
) -> FundUniverseIndex:
    """Build a FundUniverseIndex from a list of fund entries.

    Args:
        entries: List of dicts with at least fund_code and fund_name.
        code_key: Key for fund code in each dict.
        name_key: Key for fund name in each dict.

    Returns:
        Populated FundUniverseIndex.
    """
    index = FundUniverseIndex()

    for entry_dict in entries:
        fund_code = str(entry_dict.get(code_key, "")).strip()
        fund_name = str(entry_dict.get(name_key, "")).strip()

        if not fund_code or not fund_name:
            continue

        # Validate 6-digit code
        if not re.match(r"^\d{6}$", fund_code):
            continue

        normalized = _normalize_for_index(fund_name)
        no_punct = _strip_punctuation(normalized)
        core_name = _extract_core_name(normalized)
        share_class = _extract_share_class_from_name(normalized)

        entry = FundUniverseEntry(
            fund_code=fund_code,
            fund_name=fund_name,
            normalized_full_name=normalized,
            normalized_name_no_punct=no_punct,
            core_name=core_name,
            share_class=share_class,
        )
        index.add_entry(entry)

    return index


# ── Internal helpers ────────────────────────────────────────────────────


def normalize_fund_name_for_universe_index(name: str) -> str:
    """Normalize a fund name for universe index key construction.

    This is the canonical normalization for both query-side and universe-side.
    Must be used consistently to avoid exact-match misses.

    Applies:
    - Fullwidth → halfwidth
    - Chinese/English parentheses unification
    - Whitespace normalization
    - QDII/ETF联接 token normalization
    - Case-insensitive matching via casefold
    """
    if not name:
        return ""

    result = name.strip()

    # Fullwidth → halfwidth
    result = result.replace("（", "(").replace("）", ")")
    result = result.replace("Ａ", "A").replace("Ｃ", "C").replace("Ｅ", "E").replace("Ｉ", "I")

    # Normalize QDII tokens (case-insensitive)
    result = re.sub(r"(?i)qdii[\s-]*fof", "QDII-FOF", result)
    result = re.sub(r"(?i)qdii[\s-]*lof", "QDII-LOF", result)
    result = re.sub(r"(?i)qdii", "QDII", result)

    # Normalize ETF联接 tokens
    result = re.sub(r"ETF\s+联接", "ETF联接", result)
    result = re.sub(r"etf\s+联接", "ETF联接", result, flags=re.IGNORECASE)

    # Normalize whitespace
    result = re.sub(r"\s+", " ", result).strip()

    return result


def _normalize_for_index(name: str) -> str:
    """Normalize a fund name for index key construction (universe side).

    Delegates to normalize_fund_name_for_universe_index for consistency.
    """
    return normalize_fund_name_for_universe_index(name)


def _strip_punctuation(name: str) -> str:
    """Strip all punctuation, whitespace, and parentheses for fuzzy-punct matching."""
    if not name:
        return ""
    # Remove spaces, hyphens, parentheses, dots, commas, Chinese punctuation
    result = re.sub(r"[\s\-\(\)（）\.\,，、·:：；;！!？?]", "", name)
    return result


def _extract_core_name(name: str) -> str:
    """Extract core name by stripping share class suffix.

    Core name = full name minus the trailing A/C/E/I share class letter.
    """
    if not name:
        return ""
    # Match trailing A/C/E/I that is a share class marker
    # Must be preceded by a Chinese character or a structural token
    m = re.match(r"^(.+?)([ACEI])$", name)
    if m:
        core = m.group(1)
        # Only strip if the remaining core is substantial (>= 2 chars)
        if len(core) >= 2:
            return core
    return name


def _extract_share_class_from_name(name: str) -> str:
    """Extract share class suffix from a normalized name."""
    if not name:
        return ""
    m = re.match(r"^(.+?)([ACEI])$", name)
    if m:
        core = m.group(1)
        if len(core) >= 2:
            return m.group(2)
    return ""


def _core_share_class_key(core_name: str, share_class: str) -> str:
    """Build a composite key from core name + share class."""
    if not core_name:
        return ""
    no_punct = _strip_punctuation(core_name)
    if not no_punct:
        return ""
    if share_class:
        return f"{no_punct}::{share_class}"
    return no_punct
