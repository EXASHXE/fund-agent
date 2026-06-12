"""Tests for docs current claims -- search for forbidden/overclaim patterns."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_FORBIDDEN_PATTERNS = [
    (r"(?i)automatic\s+trading", "automatic trading"),
    (r"(?i)executes?\s+orders", "executes orders"),
    (r"(?i)guaranteed?\s+real-?time\s+data", "guaranteed real-time data"),
    (r"(?i)eastmoney\s+fully\s+supported", "Eastmoney fully supported"),
    (r"(?i)xueqiu\s+fully\s+supported", "Xueqiu fully supported"),
    (r"(?i)no\s+api\s+key\s+required\s+for\s+(?:eastmoney|xueqiu)", "no API key required for provider with unknown status"),
]

_OVERCLAIM_PATTERNS = [
    (r"(?i)live\s+news\s+built\s+into\s+core", "live news built into core"),
    (r"(?i)custom\s+opencode\s+plugin\s+tools?\s+verified", "custom OpenCode plugin tools verified"),
]


def _md_files() -> list[Path]:
    files: list[Path] = []
    for d in (ROOT / "docs", ROOT / "skills", ROOT / "examples"):
        if d.exists():
            files.extend(d.rglob("*.md"))
    for name in ("README.md", "AGENTS.md"):
        p = ROOT / name
        if p.exists():
            files.append(p)
    return sorted(files)


class TestDocsNoForbiddenClaims:
    @pytest.fixture(scope="class")
    def md_contents(self) -> dict[str, str]:
        contents: dict[str, str] = {}
        for f in _md_files():
            try:
                contents[str(f.relative_to(ROOT))] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return contents

    def test_no_automatic_trading(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)automatic\s+trading", content), \
                f"{path}: forbidden 'automatic trading' claim"

    def test_no_executes_orders(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)executes?\s+orders", content), \
                f"{path}: forbidden 'executes orders' claim"

    def test_no_guaranteed_realtime(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)guaranteed?\s+real-?time\s+data", content), \
                f"{path}: forbidden 'guaranteed real-time data' claim"

    def test_no_eastmoney_fully_supported(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)eastmoney\s+fully\s+supported", content), \
                f"{path}: overclaim 'Eastmoney fully supported'"

    def test_no_xueqiu_fully_supported(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)xueqiu\s+fully\s+supported", content), \
                f"{path}: overclaim 'Xueqiu fully supported'"

    def test_no_api_key_required_for_unknown_providers(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)no\s+api\s+key\s+required\s+for\s+(?:eastmoney|xueqiu)", content), \
                f"{path}: overclaim about API key requirements"

    def test_no_live_news_in_core(self, md_contents):
        for path, content in md_contents.items():
            assert not re.search(r"(?i)live\s+news\s+built\s+into\s+core", content), \
                f"{path}: overclaim 'live news built into core'"

    def test_no_broker_execution(self, md_contents):
        for path, content in md_contents.items():
            if "docs/archive/" in path:
                continue
            matches = re.findall(r"(?i)broker[\s-]+execution", content)
            for m in matches:
                idx = content.index(m)
                surrounding = content[max(0, idx - 200):idx + 200]
                lower = surrounding.lower()
                negation_present = any(
                    neg in lower for neg in (
                        "no broker", "not a broker", "without broker",
                        "no network", "no provider", "not execute",
                        "does not", "does not execute", "not execute broker",
                        "do not", "not contain",
                    )
                )
                assert negation_present, \
                    f"{path}: broker execution mentioned without negation context"
