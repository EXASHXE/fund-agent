"""CLI entrypoint tests — verify official CLI entrypoint works."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestCLIEntrypoint:
    """Verify python -m fund_agent.cli and pyproject console script target."""

    def test_python_m_fund_agent_help(self):
        """python -m fund_agent --help must work (via __main__.py)."""
        result = subprocess.run(
            [sys.executable, "-m", "fund_agent", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"CLI --help failed: {result.stderr}"
        assert "fund-agent" in result.stdout.lower() or "analyze-portfolio" in result.stdout.lower()

    def test_python_m_fund_agent_analyze_portfolio_help(self):
        """python -m fund_agent analyze-portfolio --help must work."""
        result = subprocess.run(
            [sys.executable, "-m", "fund_agent", "analyze-portfolio", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"analyze-portfolio --help failed: {result.stderr}"
        assert "--input" in result.stdout

    def test_fund_agent_cli_shim_importable(self):
        """fund_agent.cli shim must be importable."""
        import importlib

        mod = importlib.import_module("fund_agent.cli")
        assert hasattr(mod, "main"), "fund_agent.cli must expose main()"
        assert hasattr(mod, "build_parser"), "fund_agent.cli must expose build_parser()"

    def test_src_fund_agent_cli_importable(self):
        """src.fund_agent.cli must be importable."""
        import importlib

        mod = importlib.import_module("src.fund_agent.cli")
        assert hasattr(mod, "main"), "src.fund_agent.cli must expose main()"

    def test_pyproject_console_script_target_valid(self):
        """pyproject.toml console script fund_agent.cli:main must resolve."""
        pyproject = REPO_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "fund-agent = \"fund_agent.cli:main\"" in content, (
            "pyproject.toml must define fund-agent = fund_agent.cli:main"
        )

    def test_shim_forwards_to_src(self):
        """fund_agent/cli.py shim must forward to src.fund_agent.cli."""
        shim = REPO_ROOT / "fund_agent" / "cli.py"
        content = shim.read_text(encoding="utf-8")
        assert "src.fund_agent.cli" in content, (
            "fund_agent/cli.py shim must import from src.fund_agent.cli"
        )
