"""Tests for the fund-agent unified CLI."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestCLIParser:
    def test_help_exits_cleanly(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_doctor_subcommand(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--pretty"])
        assert args.command == "doctor"
        assert args.pretty is True

    def test_doctor_json_flag(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--json"])
        assert args.json_output is True

    def test_run_skill_subcommand(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run-skill", "--skill", "fund_analysis"])
        assert args.command == "run-skill"
        assert args.skill == "fund_analysis"

    def test_regressions_subcommand(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["regressions", "--pretty"])
        assert args.command == "regressions"
        assert args.pretty is True

    def test_regressions_scenario(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["regressions", "--scenario", "mixed_portfolio_report_only_zh"])
        assert args.scenario == "mixed_portfolio_report_only_zh"

    def test_provider_smoke_subcommand(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["provider-smoke", "--provider", "akshare"])
        assert args.command == "provider-smoke"
        assert args.provider == "akshare"

    def test_audit_subcommand(self):
        from src.fund_agent.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["audit", "--pretty"])
        assert args.command == "audit"
        assert args.pretty is True

    def test_no_command_returns_zero(self):
        from src.fund_agent.cli import main
        result = main([])
        assert result == 0


class TestOldScriptsStillWork:
    def test_run_skill_wrapper_importable(self):
        from scripts.run_skill import main
        assert callable(main)

    def test_doctor_wrapper_importable(self):
        from scripts.fund_agent_doctor import main
        assert callable(main)

    def test_regressions_script_importable(self):
        from scripts.run_personal_regressions import main
        assert callable(main)
