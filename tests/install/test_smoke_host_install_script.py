"""Tests for the source-checkout host smoke script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = ROOT / "scripts" / "smoke_host_install.py"


def test_smoke_script_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    assert result.returncode == 0, f"Smoke script failed:\n{result.stdout}\n{result.stderr}"


def test_smoke_script_mentions_skills():
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    output = result.stdout + result.stderr
    for skill in ["fund_analysis", "decision_support", "thesis_generation", "news_research", "sentiment_analysis"]:
        assert skill in output, f"Smoke output missing skill: {skill}"


def test_smoke_script_no_network_references():
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")
    banned = ["requests", "httpx", "aiohttp", "urllib3", "socket", "tavily", "finnhub", "openai", "anthropic"]
    for word in banned:
        assert word not in source, f"Smoke script contains banned import: {word}"


def test_smoke_script_no_provider_sdks():
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")
    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    providers = ["tavily", "finnhub", "firecrawl", "akshare", "langchain"]
    for line in import_lines:
        for p in providers:
            assert p not in line.lower(), f"Smoke script imports provider SDK: {p}"
