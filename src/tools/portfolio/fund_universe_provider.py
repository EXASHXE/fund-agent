"""M7.19: Fund universe providers for exact identity lookup.

Providers:
- AkShareFundUniverseProvider: Loads fund universe from akshare fund_name_em
- LocalPublicFundUniverseSupplementProvider: Loads public supplement from CSV
- CompositeFundUniverseProvider: Merges multiple providers into unified universe

Key invariants:
- Supplement entries must have 6-digit fund_code and at least one name field.
- Supplement entries must have a public source (eastmoney/fund_company/tiantian).
- confidence=low supplement entries do NOT auto-verify.
- No private data (holdings, NAV, shares, amounts) in supplement.
- Oracle data is NEVER used as supplement source.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


# ── Supplement confidence levels ───────────────────────────────────────

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
_VALID_CONFIDENCE_LEVELS = frozenset({CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW})

# Public sources allowed for supplement entries
ALLOWED_PUBLIC_SOURCES = frozenset({
    "eastmoney",
    "fund_company",
    "tiantian",
    "howbuy",
    "morningstar_cn",
    "csindex",
    "sse",
    "szse",
    "amac",
})


@dataclass
class FundUniverseEntryData:
    """A single fund universe entry from any provider."""

    fund_code: str
    fund_name: str = ""
    fund_full_name: str = ""
    fund_short_name: str = ""
    source: str = ""
    confidence: str = CONFIDENCE_HIGH
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_name(self) -> str:
        """Best available name for this entry."""
        return self.fund_name or self.fund_full_name or self.fund_short_name


class FundUniverseProvider(Protocol):
    """Protocol for fund universe data providers."""

    def load_entries(self) -> list[FundUniverseEntryData]:
        """Load fund universe entries from this provider."""
        ...

    def get_diagnostics(self) -> dict[str, Any]:
        """Return provider diagnostics."""
        ...


class AkShareFundUniverseProvider:
    """Loads fund universe from akshare fund_name_em."""

    _provider_name = "akshare_fund_universe"

    def __init__(self) -> None:
        self._diagnostics: dict[str, Any] = {
            "provider": self._provider_name,
            "loaded": False,
            "entry_count": 0,
        }

    def load_entries(self) -> list[FundUniverseEntryData]:
        try:
            import akshare as ak
        except ImportError:
            self._diagnostics["error"] = "akshare not installed"
            return []

        try:
            df = ak.fund_name_em()
        except Exception as exc:
            self._diagnostics["error"] = str(exc)
            return []

        entries = []
        for _, row in df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            name = str(row.get("基金简称", "")).strip()
            if code and name and re.match(r"^\d{6}$", code):
                entries.append(FundUniverseEntryData(
                    fund_code=code,
                    fund_name=name,
                    source=self._provider_name,
                    confidence=CONFIDENCE_HIGH,
                ))

        self._diagnostics["loaded"] = True
        self._diagnostics["entry_count"] = len(entries)
        return entries

    def get_diagnostics(self) -> dict[str, Any]:
        return dict(self._diagnostics)


class LocalPublicFundUniverseSupplementProvider:
    """Loads public supplement fund universe from CSV.

    CSV schema: fund_code,fund_name,fund_full_name,fund_short_name,
                source,source_url,source_date,confidence,notes

    Constraints:
    - fund_code must be 6-digit
    - fund_name or fund_full_name must be non-empty
    - source must be a public source (eastmoney/fund_company/tiantian etc.)
    - confidence must be high/medium/low
    - confidence=low entries are loaded but flagged (not auto-verified)
    - No private data allowed (no holdings, NAV, shares, amounts)
    """

    _provider_name = "local_public_fund_universe_supplement"

    def __init__(self, csv_path: Path | str) -> None:
        self._csv_path = Path(csv_path)
        self._diagnostics: dict[str, Any] = {
            "provider": self._provider_name,
            "loaded": False,
            "entry_count": 0,
            "rejected_count": 0,
            "rejection_reasons": {},
            "csv_path": str(self._csv_path),
        }

    def load_entries(self) -> list[FundUniverseEntryData]:
        if not self._csv_path.exists():
            self._diagnostics["error"] = "file not found"
            return []

        entries = []
        rejected = 0
        rejection_reasons: dict[str, int] = {}

        with open(self._csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("fund_code", "").strip()
                name = row.get("fund_name", "").strip()
                full_name = row.get("fund_full_name", "").strip()
                short_name = row.get("fund_short_name", "").strip()
                source = row.get("source", "").strip().lower()
                confidence = row.get("confidence", CONFIDENCE_HIGH).strip().lower()

                # Validate fund_code
                if not re.match(r"^\d{6}$", code):
                    rejected += 1
                    rejection_reasons["invalid_code"] = rejection_reasons.get("invalid_code", 0) + 1
                    continue

                # Validate at least one name
                if not name and not full_name and not short_name:
                    rejected += 1
                    rejection_reasons["no_name"] = rejection_reasons.get("no_name", 0) + 1
                    continue

                # Validate source is public
                if not source or source not in ALLOWED_PUBLIC_SOURCES:
                    rejected += 1
                    rejection_reasons["invalid_source"] = rejection_reasons.get("invalid_source", 0) + 1
                    continue

                # Validate confidence
                if confidence not in _VALID_CONFIDENCE_LEVELS:
                    rejected += 1
                    rejection_reasons["invalid_confidence"] = rejection_reasons.get("invalid_confidence", 0) + 1
                    continue

                entries.append(FundUniverseEntryData(
                    fund_code=code,
                    fund_name=name,
                    fund_full_name=full_name,
                    fund_short_name=short_name,
                    source=source,
                    confidence=confidence,
                    extra={
                        "source_url": row.get("source_url", "").strip(),
                        "source_date": row.get("source_date", "").strip(),
                        "notes": row.get("notes", "").strip(),
                    },
                ))

        self._diagnostics["loaded"] = True
        self._diagnostics["entry_count"] = len(entries)
        self._diagnostics["rejected_count"] = rejected
        self._diagnostics["rejection_reasons"] = rejection_reasons
        return entries

    def get_diagnostics(self) -> dict[str, Any]:
        return dict(self._diagnostics)


class CompositeFundUniverseProvider:
    """Merges entries from multiple fund universe providers.

    Deduplication: if multiple providers supply the same fund_code,
    the first provider's entry wins (preserving priority order).
    """

    _provider_name = "composite_fund_universe"

    def __init__(self, providers: list[FundUniverseProvider]) -> None:
        self._providers = providers
        self._diagnostics: dict[str, Any] = {
            "provider": self._provider_name,
            "loaded": False,
            "total_entry_count": 0,
            "provider_diagnostics": [],
            "universe_source_counts": {},
        }

    def load_entries(self) -> list[FundUniverseEntryData]:
        seen_codes: set[str] = set()
        merged: list[FundUniverseEntryData] = []
        source_counts: dict[str, int] = {}

        for provider in self._providers:
            try:
                entries = provider.load_entries()
            except Exception as exc:
                entries = []
                self._diagnostics.setdefault("provider_errors", []).append(str(exc))

            provider_diag = provider.get_diagnostics()
            self._diagnostics["provider_diagnostics"].append(provider_diag)

            for entry in entries:
                if entry.fund_code in seen_codes:
                    continue
                seen_codes.add(entry.fund_code)
                merged.append(entry)
                src = entry.source or provider_diag.get("provider", "unknown")
                source_counts[src] = source_counts.get(src, 0) + 1

        self._diagnostics["loaded"] = True
        self._diagnostics["total_entry_count"] = len(merged)
        self._diagnostics["universe_source_counts"] = source_counts
        return merged

    def get_diagnostics(self) -> dict[str, Any]:
        return dict(self._diagnostics)


def supplement_contains_no_private_fields(entries: list[FundUniverseEntryData]) -> bool:
    """Validate that supplement entries contain no private fields.

    Private fields: holdings, NAV, shares, amounts, transaction data.
    """
    private_patterns = re.compile(
        r"(nav|份额|金额|持仓|持有|交易|赎回|买入|卖出|收益|利润|成本|净值)",
        re.IGNORECASE,
    )
    for entry in entries:
        for name in (entry.fund_name, entry.fund_full_name, entry.fund_short_name):
            # Name fields can contain fund type words like "债券" — that's fine.
            # We check extra fields for private data patterns.
            pass
        for key, value in entry.extra.items():
            if private_patterns.search(str(key)) or private_patterns.search(str(value)):
                return False
    return True
