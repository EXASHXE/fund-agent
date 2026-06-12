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
    (r"(?i)researchos\s+runtime", "ResearchOS runtime (historical only)"),
    (r"(?i)planner\s+loop", "planner loop (use 'autonomous agent' instead)"),
]

_REQUIRED_CLAIMS = [
    (r"no\s+broker\s+execution", "no broker execution boundary"),
    (r"(?i)no[\s-]?network", "no-network core boundary"),
    (r"(?i)host[\s-]owned\s+(?:live\s+)?data", "host-owned data boundary"),
    (r"(?i)optional.*prototype|prototype.*optional", "provider adapters optional/prototype"),
    (r"(?i)decision_support.*formal\s+decision|formal\s+decision.*decision_support", "decision_support is formal decision runtime"),
    (r"(?i)fund_analysis.*analysis.*report\s+only|report[\s-]only.*fund_analysis", "fund_analysis is analysis/report only"),
    (r"(?i)host[\s-]owned.*(?:news|mcp|api).*key|news.*mcp.*(?:credential|key).*host", "news MCP/API credentials are host-owned"),
    (r"fund_agent\.\w+", "fund_agent.* public API"),
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

    def test_no_researchos_runtime_claim(self, md_contents):
        for path, content in md_contents.items():
            if "docs/archive/" in path or "CHANGELOG" in path:
                continue
            assert not re.search(r"(?i)researchos\s+runtime", content), \
                f"{path}: overclaim 'ResearchOS runtime' (use 'historical' or 'host')"

    def test_no_planner_loop_claim(self, md_contents):
        for path, content in md_contents.items():
            if "docs/archive/" in path or "CHANGELOG" in path:
                continue
            assert not re.search(r"(?i)planner\s+loop", content), \
                f"{path}: overclaim 'planner loop' (use 'autonomous agent' instead)"

    def test_required_no_broker_execution(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"no\s+broker\s+execution", readme, re.IGNORECASE), \
            "README.md: missing 'no broker execution' boundary"

    def test_required_no_network_core(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)no[\s-]?network", readme), \
            "README.md: missing 'no-network' core boundary"

    def test_required_host_owned_data(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)host[\s-]owned", readme), \
            "README.md: missing 'host-owned' data boundary"

    def test_required_provider_optional_prototype(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)(optional|prototype).*adapter|adapter.*(optional|prototype)", readme), \
            "README.md: missing 'optional/prototype' provider adapter status"

    def test_required_decision_support_formal(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)decision_support.*formal|formal.*decision.*decision_support", readme), \
            "README.md: missing decision_support as formal decision runtime"

    def test_required_fund_analysis_report_only(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)report[\s-]only", readme), \
            "README.md: missing report-only behavior description"

    def test_required_host_owned_news_keys(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"(?i)host[\s-]owned.*(?:news|mcp|api|credential)|news.*mcp.*host", readme), \
            "README.md: missing host-owned news/MCP/API key boundary"

    def test_required_fund_agent_public_api(self, md_contents):
        readme = md_contents.get("README.md", "")
        assert re.search(r"fund_agent\.\w+", readme), \
            "README.md: missing fund_agent.* public API references"
