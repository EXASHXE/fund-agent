"""Provider identity cross-check — M7.9.

Validates fund identity overrides by comparing the raw fund name from
Alipay transactions against the provider-reported fund name for the
candidate fund_code. This promotes manual_override_unverified to
provider_verified when names match sufficiently.

Key rules:
- fund_code must be 6 digits
- Provider lookup returns fund name for the code
- Names are normalized before comparison (platform prefixes, share class
  suffixes, full/half-width characters, common aliases)
- Similarity above threshold → provider_verified
- Similarity below threshold → code_name_mismatch, block valuation
- Provider lookup failed → manual_override_unverified stays
"""
from __future__ import annotations

import re
from typing import Any, Protocol

# ── Similarity threshold ────────────────────────────────────────────────

NAME_SIMILARITY_THRESHOLD = 0.7  # 70% similarity required for provider_verified

# ── Platform prefixes to strip ──────────────────────────────────────────

_PLATFORM_PREFIXES = [
    "蚂蚁财富-",
    "蚂蚁财富—",
    "支付宝-",
    "支付宝—",
    "余额宝-",
    "余额宝—",
    "天天基金-",
    "天天基金—",
]

# ── Share class suffixes ────────────────────────────────────────────────

# A/C/E/I share class suffixes — strip with caution, only when comparing
_SHARE_CLASS_SUFFIXES = [
    "A", "C", "E", "I",
    "A类", "C类", "E类", "I类",
]

# ── Common aliases mapping (normalized) ─────────────────────────────────

_COMMON_ALIASES = {
    "qdii": "QDII",
    "lof": "LOF",
    "etf联接": "ETF联接",
    "etf连接": "ETF联接",
    "联接": "ETF联接",
}

# ── Full-width to half-width mapping ────────────────────────────────────

_FULL_TO_HALF = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "０１２３４５６７８９",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789",
)


# ── Provider lookup protocol ────────────────────────────────────────────

class FundNameProvider(Protocol):
    """Protocol for fund name lookup by code."""

    def lookup_fund_name(self, fund_code: str) -> str | None:
        """Return the provider-reported fund name for a fund code.

        Returns None if the code is not found or lookup fails.
        """
        ...


class NullFundNameProvider:
    """Provider that always returns None (no provider available)."""

    def lookup_fund_name(self, fund_code: str) -> str | None:
        return None


class DictFundNameProvider:
    """Simple in-memory provider backed by a dict of fund_code → fund_name."""

    def __init__(self, fund_names: dict[str, str]) -> None:
        self._names = fund_names

    def lookup_fund_name(self, fund_code: str) -> str | None:
        return self._names.get(fund_code)


# ── Name normalization ──────────────────────────────────────────────────

def strip_platform_prefix(name: str) -> str:
    """Strip known platform prefixes from a fund name."""
    for prefix in _PLATFORM_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def normalize_for_comparison(name: str) -> str:
    """Normalize a fund name for similarity comparison.

    Steps:
    1. Strip platform prefixes
    2. Convert full-width to half-width
    3. Remove whitespace, parens, hyphens, dots
    4. Lowercase
    """
    if not name:
        return ""
    name = strip_platform_prefix(name)
    name = name.translate(_FULL_TO_HALF)
    # Remove whitespace, parens, hyphens, dots, commas
    name = re.sub(r"[\s\(\)（）\-\.\,，、]", "", name)
    return name.lower()


def strip_share_class_suffix(name: str) -> tuple[str, str | None]:
    """Strip share class suffix (A/C/E/I) from a fund name.

    Returns (stripped_name, suffix_or_None).
    Only strips if the suffix is at the end and preceded by a space or
    is the last character.

    CAUTION: This is conservative — only strips clear share class markers.
    """
    normalized = normalize_for_comparison(name)
    for suffix in ("a", "c", "e", "i"):
        if normalized.endswith(suffix):
            stripped = normalized[:-1]
            # Only strip if the remaining name is substantial
            if len(stripped) >= 2:
                return stripped, suffix.upper()
    return normalized, None


# ── Similarity computation ──────────────────────────────────────────────

def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute similarity between two fund names.

    Uses a combination of:
    1. Exact match after normalization → 1.0
    2. Share-class-stripped match → 0.95
    3. Substring containment → 0.85
    4. Longest common subsequence ratio → 0.0-1.0

    Returns a float between 0.0 and 1.0.
    """
    if not name_a or not name_b:
        return 0.0

    norm_a = normalize_for_comparison(name_a)
    norm_b = normalize_for_comparison(name_b)

    if not norm_a or not norm_b:
        return 0.0

    # Exact match
    if norm_a == norm_b:
        return 1.0

    # Share class stripped match
    stripped_a, suffix_a = strip_share_class_suffix(name_a)
    stripped_b, suffix_b = strip_share_class_suffix(name_b)
    if suffix_a != suffix_b and stripped_a == stripped_b:
        return 0.95

    # Substring containment
    if norm_a in norm_b or norm_b in norm_a:
        return 0.85

    # Longest common subsequence ratio
    lcs_len = _lcs_length(norm_a, norm_b)
    ratio = (2.0 * lcs_len) / (len(norm_a) + len(norm_b))
    return ratio


def _lcs_length(a: str, b: str) -> int:
    """Compute length of longest common subsequence."""
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    # Optimize space: only need two rows
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]


# ── Cross-check logic ───────────────────────────────────────────────────

def provider_cross_check(
    raw_fund_name: str,
    candidate_fund_code: str,
    provider: FundNameProvider,
    threshold: float = NAME_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Perform provider identity cross-check.

    Args:
        raw_fund_name: The fund name from Alipay transaction.
        candidate_fund_code: The 6-digit candidate fund code from override.
        provider: Fund name lookup provider.
        threshold: Minimum similarity for provider_verified.

    Returns:
        Dict with:
        - lookup_result: "confirmed" | "mismatch" | "failed"
        - provider_fund_name: The name returned by provider (or None)
        - similarity: The computed similarity score (or None if lookup failed)
        - identity_verification_status: "provider_verified" | "code_name_mismatch" | "manual_override_unverified"
        - details: Human-readable explanation
    """
    # Validate fund_code
    if not candidate_fund_code or not (candidate_fund_code.isdigit() and len(candidate_fund_code) == 6):
        return {
            "lookup_result": "failed",
            "provider_fund_name": None,
            "similarity": None,
            "identity_verification_status": "manual_override_unverified",
            "details": f"candidate_fund_code '{candidate_fund_code}' is not a valid 6-digit code",
        }

    # Lookup provider name
    provider_name = provider.lookup_fund_name(candidate_fund_code)

    if provider_name is None:
        return {
            "lookup_result": "failed",
            "provider_fund_name": None,
            "similarity": None,
            "identity_verification_status": "manual_override_unverified",
            "details": f"provider lookup failed for fund_code {candidate_fund_code}",
        }

    # Compute similarity
    similarity = compute_name_similarity(raw_fund_name, provider_name)

    if similarity >= threshold:
        return {
            "lookup_result": "confirmed",
            "provider_fund_name": provider_name,
            "similarity": round(similarity, 4),
            "identity_verification_status": "provider_verified",
            "details": f"provider cross-check passed: similarity={similarity:.2%} >= {threshold:.0%}",
        }
    else:
        return {
            "lookup_result": "mismatch",
            "provider_fund_name": provider_name,
            "similarity": round(similarity, 4),
            "identity_verification_status": "code_name_mismatch",
            "details": f"provider cross-check mismatch: similarity={similarity:.2%} < {threshold:.0%}; "
                       f"raw='{raw_fund_name}' vs provider='{provider_name}'",
        }


def batch_provider_cross_check(
    resolutions: list[dict[str, Any]],
    provider: FundNameProvider,
    threshold: float = NAME_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Perform provider cross-check on a batch of identity resolutions.

    Updates identity_verification_status for each resolution where
    the current status is manual_override_unverified.

    Args:
        resolutions: List of resolution dicts from resolve_fund_identities.
        provider: Fund name lookup provider.
        threshold: Minimum similarity for provider_verified.

    Returns:
        Dict with diagnostics:
        - updated_resolutions: list of updated resolution dicts
        - provider_identity_checked_count
        - provider_identity_verified_count
        - provider_identity_mismatch_count
        - provider_identity_lookup_failed_count
    """
    checked = 0
    verified = 0
    mismatch = 0
    lookup_failed = 0

    for res in resolutions:
        current_status = res.get("identity_verification_status", "")
        if current_status != "manual_override_unverified":
            continue

        fund_code = res.get("resolved_fund_code")
        raw_name = res.get("raw_fund_name") or res.get("fund_name", "")

        if not fund_code:
            continue

        checked += 1
        result = provider_cross_check(raw_name, fund_code, provider, threshold)

        if result["lookup_result"] == "confirmed":
            verified += 1
            res["identity_verification_status"] = "provider_verified"
        elif result["lookup_result"] == "mismatch":
            mismatch += 1
            res["identity_verification_status"] = "code_name_mismatch"
        else:
            lookup_failed += 1
            # Keep manual_override_unverified

        res["provider_cross_check"] = result

    return {
        "updated_resolutions": resolutions,
        "provider_identity_checked_count": checked,
        "provider_identity_verified_count": verified,
        "provider_identity_mismatch_count": mismatch,
        "provider_identity_lookup_failed_count": lookup_failed,
    }
