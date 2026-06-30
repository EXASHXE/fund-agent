"""M7.11 Fund identity candidate discovery from names.

When no fund_identity_overrides are available, discovers candidate fund codes
from provider name search. Uses injected FundIdentitySearchProvider — core
never imports akshare directly.

Key invariants:
- Only unique high-confidence matches auto-promote to provider_verified.
- Ambiguous / low-confidence / share-class-mismatched candidates stay unverified.
- Candidate codes are never displayed as confirmed codes in public output.
- Transaction-derived reconstruction only proceeds after identity verified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


# ── Candidate data structures ──────────────────────────────────────────


@dataclass
class FundIdentityCandidate:
    """A single candidate fund code from name search."""

    fund_code: str
    fund_name: str
    fund_type: str = ""
    share_class: str = ""
    source: str = ""
    match_score: float = 0.0
    match_bucket: str = ""
    match_reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    # M7.15 strict identity fields
    hard_reject: bool = False
    reject_reasons: list[str] = field(default_factory=list)
    critical_token_mismatch: list[str] = field(default_factory=list)
    identity_token_overlap: float = 0.0
    candidate_status: str = "accepted_candidate"


# ── Match buckets ──────────────────────────────────────────────────────

BUCKET_EXACT = "exact"
BUCKET_HIGH = "high"
BUCKET_MEDIUM = "medium"
BUCKET_LOW = "low"
BUCKET_AMBIGUOUS = "ambiguous"
BUCKET_MISMATCH = "mismatch"

ALL_BUCKETS = frozenset({
    BUCKET_EXACT, BUCKET_HIGH, BUCKET_MEDIUM, BUCKET_LOW,
    BUCKET_AMBIGUOUS, BUCKET_MISMATCH,
})

# ── Auto-verify thresholds ─────────────────────────────────────────────

AUTO_VERIFY_MIN_SCORE = 0.85
AUTO_VERIFY_MIN_MARGIN = 0.20

# ── M7.16 Exact match reasons (must match akshare_name_search_provider) ──

EXACT_FUND_UNIVERSE_NAME_MATCH = "exact_fund_universe_name_match"
EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH = "exact_fund_universe_name_without_punctuation_match"
EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH = "exact_core_name_and_share_class_match"
EXACT_LOCAL_CACHE_NAME_MATCH = "exact_local_cache_name_match"

_EXACT_MATCH_REASONS = frozenset({
    EXACT_FUND_UNIVERSE_NAME_MATCH,
    EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH,
    EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH,
    EXACT_LOCAL_CACHE_NAME_MATCH,
})


# ── Provider abstraction ───────────────────────────────────────────────


class FundIdentitySearchProvider(Protocol):
    """Protocol for fund identity search providers.

    Implementations may call external APIs (akshare, etc.) but must be
    injected — core never imports providers directly.
    """

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        """Search for fund codes matching a normalized name.

        Returns candidates sorted by relevance (best first).
        """
        ...


class NullFundIdentitySearchProvider:
    """No-op provider for tests and offline mode."""

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        return []


# ── Name extraction from Alipay raw names ──────────────────────────────

_ALIPAY_PREFIX = "蚂蚁财富-"

_ALIPAY_ACTION_SUFFIXES = [
    "卖出至余额宝",
    "现金分红至余额宝",
    "确认成功退款",
    "转换退款",
    "买入退款",
    "份额确认中",
    "活动赠送",
    "定投",
    "买入",
    "卖出",
    "转换",
    "分红",
    "赎回",
]

# Tokens that indicate fund characteristics
QDII_TOKENS = frozenset({"qdii", "qdii-fof", "qdii-lof"})
ETF_LINK_TOKENS = frozenset({"etf联接", "etf 联接", "联接"})

# Share class suffixes (A/C/E are the common ones for CN funds)
SHARE_CLASS_PATTERN = r"[ACEace]$"

# ── M7.15 Strict identity tokens ────────────────────────────────────────

# Brand / fund company tokens — different brands must not match
BRAND_TOKENS: dict[str, str] = {
    "万家": "万家", "华宝": "华宝", "华夏": "华夏", "华安": "华安",
    "国泰": "国泰", "天弘": "天弘", "东方": "东方", "建信": "建信",
    "嘉实": "嘉实", "摩根": "摩根", "易方达": "易方达", "永赢": "永赢",
    "广发": "广发", "工银": "工银", "南方": "南方", "博时": "博时",
    "招商": "招商", "鹏华": "鹏华", "富国": "富国", "汇添富": "汇添富",
    "中欧": "中欧", "兴全": "兴全", "景顺": "景顺", "交银": "交银",
    "银华": "银华", "诺安": "诺安", "平安": "平安", "前海开源": "前海开源",
}

# Theme / industry tokens — conflicting themes must not match
THEME_TOKENS: dict[str, str] = {
    "黄金": "黄金", "消费电子": "消费电子", "创新药": "创新药",
    "医药": "医药", "油气": "油气", "石油天然气": "石油天然气",
    "光伏": "光伏", "新能源车": "新能源车", "电池": "电池",
    "红利": "红利", "短债": "短债", "纳斯达克": "纳斯达克",
    "全球新兴市场": "全球新兴市场", "新能源汽车": "新能源汽车",
    "电子": "电子", "半导体": "半导体", "芯片": "芯片",
    "白酒": "白酒", "军工": "军工", "银行": "银行",
    "券商": "券商", "房地产": "房地产", "基建": "基建",
    "环保": "环保", "人工智能": "人工智能", "机器人": "机器人",
    "消费": "消费", "科技": "科技", "医药生物": "医药生物",
    "港股": "港股", "沪港深": "沪港深", "中美互联网": "中美互联网",
}

# Structure tokens — QDII/non-QDII, ETF联接/non-ETF联接 must not cross
STRUCTURE_TOKENS: dict[str, str] = {
    "ETF联接": "ETF联接", "ETF": "ETF", "LOF": "LOF",
    "QDII": "QDII", "债券": "债券", "短债": "短债",
    "混合": "混合", "指数": "指数", "股票": "股票",
    "双债增强": "双债增强", "纯债": "纯债",
}


def extract_fund_name_from_alipay_item(
    product_name: str,
) -> dict[str, Any]:
    """Extract fund name and role from an Alipay product name string.

    Returns:
        dict with keys:
        - raw_name: original product_name
        - normalized_name: cleaned fund name
        - extracted_role: "primary" | "conversion_source" | "conversion_target"
        - conversion_target_name: name of target fund (if conversion)
    """
    raw_name = product_name.strip()
    name = raw_name
    conversion_target_name = None
    extracted_role = "primary"

    # Strip leading prefix
    if name.startswith(_ALIPAY_PREFIX):
        name = name[len(_ALIPAY_PREFIX):]

    # Handle conversion patterns:
    # "FundA-[转换至]FundB-suffix" or "FundA[转换至]FundB"
    conv_match = _match_conversion_pattern(name)
    if conv_match:
        source_name = conv_match["source"]
        target_name = conv_match["target"]
        name = source_name
        conversion_target_name = target_name
        extracted_role = "conversion_source"

    # Strip trailing action suffix (longest match first)
    for suffix in _ALIPAY_ACTION_SUFFIXES:
        if name.endswith("-" + suffix):
            name = name[: -(len(suffix) + 1)]
            break

    # Also strip bare suffix without hyphen (e.g. "定投" at end)
    for suffix in ["定投"]:
        if name.endswith(suffix) and not name.endswith("-" + suffix):
            name = name[: -len(suffix)]
            break

    normalized = normalize_fund_name_for_search(name.strip())

    result: dict[str, Any] = {
        "raw_name": raw_name,
        "normalized_name": normalized,
        "extracted_role": extracted_role,
        "conversion_target_name": None,
    }

    if conversion_target_name:
        result["conversion_target_name"] = normalize_fund_name_for_search(conversion_target_name)

    return result


def _match_conversion_pattern(name: str) -> dict[str, str] | None:
    """Match conversion patterns like 'FundA-[转换至]FundB' or 'FundA[转换至]FundB'.

    Returns dict with 'source' and 'target' keys, or None.
    """
    import re

    # Pattern: "FundA-[转换至]FundB" or "FundA[转换至]FundB"
    m = re.match(r"^(.+?)(?:-?\[转换至\])(.+?)(?:-.+)?$", name)
    if m:
        return {"source": m.group(1).strip(), "target": m.group(2).strip()}
    return None


def normalize_fund_name_for_search(name: str) -> str:
    """Normalize a fund name for search matching.

    Applies:
    - Fullwidth → halfwidth unification
    - Chinese/English parentheses unification
    - Whitespace normalization
    - QDII/ETF联接 token normalization
    - Preserves share class suffix (A/C/E)
    """
    import re

    if not name:
        return ""

    result = name.strip()

    # Fullwidth → halfwidth
    result = result.replace("（", "(").replace("）", ")")
    result = result.replace("Ａ", "A").replace("Ｃ", "C").replace("Ｅ", "E")

    # Normalize QDII tokens
    result = re.sub(r"(?i)qdii[\s-]*fof", "QDII-FOF", result)
    result = re.sub(r"(?i)qdii[\s-]*lof", "QDII-LOF", result)
    result = re.sub(r"(?i)qdii", "QDII", result)

    # Normalize ETF联接 tokens
    result = re.sub(r"ETF\s+联接", "ETF联接", result)

    # Normalize whitespace
    result = re.sub(r"\s+", " ", result).strip()

    return result


def extract_share_class(name: str) -> str:
    """Extract share class suffix from a fund name (A/C/E)."""
    import re

    if not name:
        return ""
    m = re.search(SHARE_CLASS_PATTERN, name)
    if m:
        return m.group(0).upper()
    return ""


def extract_qdii_token(name: str) -> str:
    """Extract QDII token from name, normalized to lowercase."""
    import re

    lower = name.lower()
    if "qdii-fof" in lower:
        return "qdii-fof"
    if "qdii-lof" in lower:
        return "qdii-lof"
    if "qdii" in lower:
        return "qdii"
    return ""


def extract_etf_link_token(name: str) -> str:
    """Extract ETF联接 token from name."""
    if "ETF联接" in name or "etf联接" in name.lower() or "ETF 联接" in name:
        return "etf联接"
    if "联接" in name:
        return "联接"
    return ""


# ── M7.15 Token extraction for strict matching ─────────────────────────


def _extract_brand_token(name: str) -> str:
    """Extract brand/fund company token from a fund name."""
    for token, key in BRAND_TOKENS.items():
        if token in name:
            return key
    return ""


def _extract_theme_tokens(name: str) -> frozenset[str]:
    """Extract theme/industry tokens from a fund name."""
    return frozenset(key for token, key in THEME_TOKENS.items() if token in name)


def _extract_structure_tokens(name: str) -> frozenset[str]:
    """Extract structure tokens from a fund name (QDII, ETF联接, 债券, etc.)."""
    return frozenset(key for token, key in STRUCTURE_TOKENS.items() if token in name)


def _compute_identity_token_overlap(
    query_name: str, candidate_name: str,
    q_brand: str, c_brand: str,
    q_themes: frozenset[str], c_themes: frozenset[str],
    q_structures: frozenset[str], c_structures: frozenset[str],
) -> float:
    """Compute identity token overlap ratio (0.0-1.0).

    Measures how many identity-critical tokens are shared vs total unique.
    """
    all_tokens: set[str] = set()
    shared_tokens: set[str] = set()

    # Brand
    if q_brand or c_brand:
        all_tokens.add("brand")
        if q_brand and c_brand and q_brand == c_brand:
            shared_tokens.add("brand")

    # Themes
    all_themes = q_themes | c_themes
    shared_themes = q_themes & c_themes
    all_tokens.update(f"theme:{t}" for t in all_themes)
    shared_tokens.update(f"theme:{t}" for t in shared_themes)

    # Structures
    all_structs = q_structures | c_structures
    shared_structs = q_structures & c_structures
    all_tokens.update(f"struct:{s}" for s in all_structs)
    shared_tokens.update(f"struct:{s}" for s in shared_structs)

    if not all_tokens:
        return 0.0
    return len(shared_tokens) / len(all_tokens)


def apply_hard_reject(
    query_name: str,
    candidate: FundIdentityCandidate,
) -> FundIdentityCandidate:
    """Apply M7.15 hard reject rules to a scored candidate.

    Hard reject if:
    1. Brand token mismatch (different fund companies)
    2. Critical theme token conflict (e.g. 消费电子 vs 黄金)
    3. Critical structure mismatch (QDII vs non-QDII, ETF联接 vs non-ETF联接)
    4. Share class mismatch (A vs C)
    """
    q_norm = normalize_fund_name_for_search(query_name)
    c_norm = normalize_fund_name_for_search(candidate.fund_name)

    reject_reasons: list[str] = []
    critical_mismatches: list[str] = []

    # 1. Brand mismatch
    q_brand = _extract_brand_token(q_norm)
    c_brand = _extract_brand_token(c_norm)
    if q_brand and c_brand and q_brand != c_brand:
        reject_reasons.append("rejected_brand_mismatch")
        critical_mismatches.append(f"brand:{q_brand}!={c_brand}")

    # 2. Theme mismatch
    q_themes = _extract_theme_tokens(q_norm)
    c_themes = _extract_theme_tokens(c_norm)
    if q_themes and c_themes:
        # If both have theme tokens but none overlap → hard reject
        if not (q_themes & c_themes):
            reject_reasons.append("rejected_theme_mismatch")
            critical_mismatches.append(f"theme:{q_themes}∩{c_themes}=∅")

    # 3. Structure mismatch
    q_structs = _extract_structure_tokens(q_norm)
    c_structs = _extract_structure_tokens(c_norm)
    q_has_qdii = "QDII" in q_structs
    c_has_qdii = "QDII" in c_structs
    q_has_etf_link = "ETF联接" in q_structs
    c_has_etf_link = "ETF联接" in c_structs
    q_has_short_debt = "短债" in q_structs
    c_has_short_debt = "短债" in c_structs

    if q_has_qdii != c_has_qdii:
        reject_reasons.append("rejected_structure_mismatch")
        critical_mismatches.append("qdii_vs_non_qdii")
    if q_has_etf_link != c_has_etf_link:
        reject_reasons.append("rejected_structure_mismatch")
        critical_mismatches.append("etf_link_vs_non_etf_link")
    # 短债 vs 双债增强/纯债 — 短债 only matches 短债
    if q_has_short_debt and not c_has_short_debt:
        reject_reasons.append("rejected_structure_mismatch")
        critical_mismatches.append("short_debt_vs_non_short_debt")

    # 4. Share class mismatch
    q_share = extract_share_class(q_norm)
    c_share = extract_share_class(c_norm)
    if q_share and c_share and q_share != c_share:
        reject_reasons.append("rejected_share_class_mismatch")
        critical_mismatches.append(f"share_class:{q_share}!={c_share}")

    # Compute identity token overlap
    token_overlap = _compute_identity_token_overlap(
        q_norm, c_norm, q_brand, c_brand,
        q_themes, c_themes, q_structs, c_structs,
    )

    # Apply hard reject
    is_hard_reject = len(reject_reasons) > 0
    status = "accepted_candidate"
    if is_hard_reject:
        # Use first reject reason to determine status
        for r in reject_reasons:
            if r in (
                "rejected_brand_mismatch", "rejected_theme_mismatch",
                "rejected_structure_mismatch", "rejected_share_class_mismatch",
            ):
                status = r
                break

    candidate.hard_reject = is_hard_reject
    candidate.reject_reasons = reject_reasons
    candidate.critical_token_mismatch = critical_mismatches
    candidate.identity_token_overlap = round(token_overlap, 4)
    candidate.candidate_status = status

    # If hard rejected, force score down
    if is_hard_reject:
        candidate.match_score = min(candidate.match_score, 0.0)
        candidate.match_bucket = BUCKET_MISMATCH

    return candidate


# ── Candidate scoring ──────────────────────────────────────────────────


def score_candidate(
    query_name: str,
    candidate: FundIdentityCandidate,
) -> FundIdentityCandidate:
    """Score a candidate against a query name using deterministic rules.

    Updates candidate.match_score, match_bucket, match_reasons, risk_flags.

    M7.16: If the candidate already has an exact universe match reason
    from the provider (e.g. exact_fund_universe_name_match), the scoring
    preserves that reason and uses the provider's score/bucket as the base.
    Additional scoring dimensions (share class, QDII, ETF联接) are still applied.
    """
    from src.tools.portfolio.provider_identity_cross_check import compute_name_similarity

    q_norm = normalize_fund_name_for_search(query_name)
    c_norm = normalize_fund_name_for_search(candidate.fund_name)

    if not q_norm or not c_norm:
        candidate.match_score = 0.0
        candidate.match_bucket = BUCKET_MISMATCH
        return candidate

    # M7.16: Check if candidate already has an exact universe match reason
    existing_exact_reasons = set(candidate.match_reasons) & _EXACT_MATCH_REASONS
    if existing_exact_reasons:
        # Preserve the provider's exact match reason and score
        reasons: list[str] = list(existing_exact_reasons)
        risk_flags: list[str] = []
        score = candidate.match_score
        name_sim = compute_name_similarity(q_norm, c_norm)
    else:
        reasons = []
        risk_flags = []
        score = 0.0

        # 1. Name similarity (LCS-based)
        name_sim = compute_name_similarity(q_norm, c_norm)

        # 2. Exact normalized match
        if q_norm == c_norm:
            score = 1.0
            reasons.append("exact_normalized_match")
        elif name_sim >= 0.95:
            score = 0.95
            reasons.append("near_exact_name_match")
        elif name_sim >= 0.85:
            score = 0.85
            reasons.append("high_name_similarity")
        elif name_sim >= 0.70:
            score = 0.70
            reasons.append("medium_name_similarity")
        elif name_sim >= 0.50:
            score = 0.50
            reasons.append("low_name_similarity")
        else:
            score = name_sim
            reasons.append("weak_name_similarity")

        # 3. Provider name contains query
        if q_norm in c_norm and "exact_normalized_match" not in reasons:
            score = max(score, 0.75)
            reasons.append("provider_name_contains_query")

        # 4. Query contains provider name
        if c_norm in q_norm and "exact_normalized_match" not in reasons:
            score = max(score, 0.70)
            reasons.append("query_contains_provider_name")

    # 5. Share class check
    q_share = extract_share_class(q_norm)
    c_share = extract_share_class(c_norm)
    if q_share and c_share:
        if q_share == c_share:
            reasons.append("share_class_exact_match")
            score = min(1.0, score + 0.05)
        else:
            risk_flags.append("share_class_mismatch")
            score *= 0.7
            reasons.append("share_class_mismatch_penalty")
    elif q_share and not c_share:
        reasons.append("query_has_share_class_candidate_does_not")
    elif c_share and not q_share:
        reasons.append("candidate_has_share_class_query_does_not")

    # 6. QDII token check
    q_qdii = extract_qdii_token(q_norm)
    c_qdii = extract_qdii_token(c_norm)
    if q_qdii and c_qdii:
        if q_qdii == c_qdii:
            reasons.append("qdii_token_match")
            score = min(1.0, score + 0.03)
        else:
            risk_flags.append("qdii_mismatch")
            score *= 0.6
            reasons.append("qdii_mismatch_penalty")
    elif q_qdii and not c_qdii:
        risk_flags.append("query_is_qdii_candidate_is_not")
        score *= 0.8
    elif c_qdii and not q_qdii:
        risk_flags.append("candidate_is_qdii_query_is_not")
        score *= 0.8

    # 7. ETF联接 token check
    q_etf = extract_etf_link_token(q_norm)
    c_etf = extract_etf_link_token(c_norm)
    if q_etf and c_etf:
        if q_etf == c_etf:
            reasons.append("etf_link_token_match")
            score = min(1.0, score + 0.03)
        else:
            risk_flags.append("etf_link_mismatch")
            score *= 0.6
            reasons.append("etf_link_mismatch_penalty")
    elif q_etf and not c_etf:
        risk_flags.append("query_is_etf_link_candidate_is_not")
        score *= 0.8
    elif c_etf and not q_etf:
        risk_flags.append("candidate_is_etf_link_query_is_not")
        score *= 0.8

    # 8. Ambiguous short name penalty
    if len(q_norm) <= 4 and name_sim < 0.90:
        score *= 0.8
        reasons.append("ambiguous_short_name_penalty")

    # 9. Fund type token match
    q_type_tokens = _extract_fund_type_tokens(q_norm)
    c_type_tokens = _extract_fund_type_tokens(c_norm)
    if q_type_tokens and c_type_tokens:
        overlap = q_type_tokens & c_type_tokens
        if overlap:
            reasons.append("fund_type_token_match")
            score = min(1.0, score + 0.02)

    # Assign bucket
    bucket = _score_to_bucket(score, reasons, risk_flags)

    candidate.match_score = round(score, 4)
    candidate.match_bucket = bucket
    candidate.match_reasons = reasons
    candidate.risk_flags = risk_flags

    return candidate


def _score_to_bucket(score: float, reasons: list[str], risk_flags: list[str]) -> str:
    """Convert score to match bucket."""
    if "exact_normalized_match" in reasons:
        return BUCKET_EXACT
    if score >= 0.85 and not risk_flags:
        return BUCKET_HIGH
    if score >= 0.85 and risk_flags:
        return BUCKET_AMBIGUOUS
    if score >= 0.70:
        return BUCKET_MEDIUM
    if score >= 0.50:
        return BUCKET_LOW
    if score > 0:
        return BUCKET_LOW
    return BUCKET_MISMATCH


_FUND_TYPE_TOKENS = frozenset({
    "债券", "货币", "股票", "混合", "指数", "fof", "lof",
    "reits", "封闭", "定期开放",
})


def _extract_fund_type_tokens(name: str) -> frozenset[str]:
    """Extract fund type tokens from a name."""
    lower = name.lower()
    return frozenset(t for t in _FUND_TYPE_TOKENS if t in lower)


# ── Auto-verify decision ───────────────────────────────────────────────


def should_auto_verify(
    candidates: list[FundIdentityCandidate],
) -> tuple[bool, str]:
    """Determine if the top candidate can be auto-verified as provider_verified.

    Returns (can_auto_verify, reason).

    M7.16: Auto-verify REQUIRES an exact match reason from the fund universe:
    - exact_fund_universe_name_match
    - exact_fund_universe_name_without_punctuation_match
    - exact_core_name_and_share_class_match

    Plus all M7.15 requirements:
    - No hard_reject
    - No critical_token_mismatch
    - identity_token_overlap > 0
    - Valid 6-digit fund_code
    - Non-empty fund_name
    - No share_class_mismatch / qdii_mismatch / etf_link_mismatch risk flags

    Prohibited auto-verify reasons (M7.16):
    - single_source_fuzzy_high_score
    - LCS high score
    - substring containment
    - identity_token_overlap > 0 alone
    """
    if not candidates:
        return False, "no_candidates"

    top = candidates[0]

    # Valid 6-digit code
    if not _is_valid_fund_code(top.fund_code):
        return False, "invalid_fund_code"

    # Must have fund_name from provider
    if not top.fund_name:
        return False, "no_provider_profile"

    # M7.15: Hard reject blocks auto-verify
    if top.hard_reject:
        return False, f"hard_reject:{','.join(top.reject_reasons)}"

    # M7.15: Critical token mismatch blocks auto-verify
    if top.critical_token_mismatch:
        return False, f"critical_token_mismatch:{','.join(top.critical_token_mismatch)}"

    # M7.15: Must have identity token overlap
    if top.identity_token_overlap <= 0:
        return False, "no_identity_token_overlap"

    # M7.16: MUST have an exact match reason from fund universe
    has_exact_reason = bool(set(top.match_reasons) & _EXACT_MATCH_REASONS)
    if not has_exact_reason:
        return False, "no_exact_universe_match_reason"

    # Score threshold
    if top.match_score < AUTO_VERIFY_MIN_SCORE:
        return False, f"score_below_threshold({top.match_score:.2f}<{AUTO_VERIFY_MIN_SCORE})"

    # Margin check
    if len(candidates) >= 2:
        margin = top.match_score - candidates[1].match_score
        if margin < AUTO_VERIFY_MIN_MARGIN:
            return False, f"insufficient_margin({margin:.2f}<{AUTO_VERIFY_MIN_MARGIN})"

    # Risk flag checks
    for flag in top.risk_flags:
        if flag in ("share_class_mismatch", "qdii_mismatch", "etf_link_mismatch"):
            return False, f"risk_flag:{flag}"

    # Bucket must be exact or high
    if top.match_bucket not in (BUCKET_EXACT, BUCKET_HIGH):
        return False, f"bucket_not_high_enough({top.match_bucket})"

    return True, "auto_verified"


def _is_valid_fund_code(code: str) -> bool:
    """Check if code is a valid 6-digit fund code."""
    import re
    return bool(re.match(r"^\d{6}$", str(code)))


# ── Discovery orchestrator ─────────────────────────────────────────────


def discover_candidates(
    raw_fund_names: list[str],
    provider: FundIdentitySearchProvider | None = None,
) -> dict[str, list[FundIdentityCandidate]]:
    """Discover fund code candidates for a list of raw fund names.

    Args:
        raw_fund_names: List of raw fund names from Alipay transactions.
        provider: Search provider (NullFundIdentitySearchProvider if None).

    Returns:
        Dict mapping normalized_name → sorted list of FundIdentityCandidate.
    """
    _provider = provider or NullFundIdentitySearchProvider()
    results: dict[str, list[FundIdentityCandidate]] = {}

    for raw_name in raw_fund_names:
        extracted = extract_fund_name_from_alipay_item(raw_name)
        norm_name = extracted["normalized_name"]

        if not norm_name or norm_name in results:
            continue

        # Search provider
        raw_candidates = _provider.search_by_name(norm_name)

        # Score each candidate
        scored = []
        for cand in raw_candidates:
            scored_cand = score_candidate(norm_name, cand)
            # M7.15: Apply hard reject after scoring
            scored_cand = apply_hard_reject(norm_name, scored_cand)
            scored.append(scored_cand)

        # Sort by score descending
        scored.sort(key=lambda c: c.match_score, reverse=True)

        results[norm_name] = scored

    return results


def compute_discovery_summary(
    discovery_results: dict[str, list[FundIdentityCandidate]],
) -> dict[str, Any]:
    """Compute summary statistics from discovery results."""
    name_search_requested_count = len(discovery_results)
    total_candidates = 0
    unique_high_confidence = 0
    ambiguous = 0
    no_result = 0
    promoted_provider_verified = 0
    unverified = 0

    for norm_name, candidates in discovery_results.items():
        total_candidates += len(candidates)
        if not candidates:
            no_result += 1
            continue

        can_verify, _ = should_auto_verify(candidates)
        if can_verify:
            promoted_provider_verified += 1
            unique_high_confidence += 1
        elif len(candidates) >= 2 and candidates[0].match_score >= 0.70:
            ambiguous += 1
            unverified += 1
        elif candidates[0].match_score >= 0.70:
            unique_high_confidence += 1
            unverified += 1  # Not auto-verified but has candidates
        else:
            unverified += 1

    return {
        "name_search_requested_count": name_search_requested_count,
        "name_search_candidate_count": total_candidates,
        "name_search_unique_high_confidence_count": unique_high_confidence,
        "name_search_ambiguous_count": ambiguous,
        "name_search_no_result_count": no_result,
        "name_search_promoted_provider_verified_count": promoted_provider_verified,
        "name_search_unverified_count": unverified,
    }
