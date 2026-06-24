#!/usr/bin/env python3
"""Shared fund identity utilities.

Provides normalization, validation, and coercion for fund codes and names
used across identity resolution, Alipay import, and portfolio reconstruction.
"""

from __future__ import annotations

import re
from typing import Any

_SIX_DIGIT_RE = re.compile(r"^\d{6}$")

# Characters stripped during fund name normalization:
# whitespace, half/full-width parens, hyphens, dots, commas (CN and EN)
_NORMALIZE_RE = re.compile(r"[\s\(\)（）\-\.\,，、]")


def normalize_fund_name(name: str) -> str:
    """Normalize a fund name for fuzzy matching.

    Strips whitespace, parentheses (half and full width), hyphens, dots,
    and commas. Does NOT strip Alipay prefixes — that is the job of
    ``_clean_fund_name`` in the import script.
    """
    if not name:
        return ""
    return _NORMALIZE_RE.sub("", name)


def is_valid_fund_code(code: Any) -> bool:
    """Return True if *code* is a non-empty string of exactly six digits."""
    if not isinstance(code, str):
        return False
    return bool(_SIX_DIGIT_RE.match(code))


def coerce_fund_code(raw: Any) -> str | None:
    """Return *raw* unchanged if it is a valid six-digit fund code, else None."""
    if is_valid_fund_code(raw):
        return raw
    return None
