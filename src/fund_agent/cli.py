"""Unified fund-agent CLI.

Subcommands:
    doctor          -- deterministic readiness check
    run-skill       -- run a manifest skill via JSON bridge
    regressions     -- run personal portfolio regression fixtures
    provider-smoke  -- optional host adapter smoke test
    audit           -- run project audit scripts

Old console scripts (fund-agent-run-skill, fund-agent-doctor) remain
compatible via their existing entry points.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _cmd_doctor(args: argparse.Namespace) -> int:
    from src.skillpack.doctor import main as doctor_main
    argv = ["--pretty"] if args.pretty else []
    if args.json_output:
        argv.append("--json")
    sys.argv = ["fund-agent-doctor"] + argv
    return doctor_main()


def _cmd_run_skill(args: argparse.Namespace) -> int:
    from src.skillpack.run_skill import main as run_skill_main
    argv = []
    if args.skill:
        argv.extend(["--skill", args.skill])
    if args.input_file:
        argv.extend(["--input", args.input_file])
    if args.pretty:
        argv.append("--pretty")
    sys.argv = ["fund-agent-run-skill"] + argv
    return run_skill_main()


def _cmd_regressions(args: argparse.Namespace) -> int:
    from scripts.run_personal_regressions import main as regressions_main
    argv = []
    if args.pretty:
        argv.append("--pretty")
    if args.scenario:
        argv.extend(["--scenario", args.scenario])
    if args.show_trace:
        argv.append("--show-trace")
    sys.argv = ["run_personal_regressions"] + argv
    return regressions_main()


def _cmd_provider_smoke(args: argparse.Namespace) -> int:
    from examples.host_data_adapters.provider_smoke import main as smoke_main
    argv = []
    if args.provider:
        argv.extend(["--provider", args.provider])
    if args.all:
        argv.append("--all")
    if args.capability:
        argv.extend(["--capability", args.capability])
    if args.fund_code:
        argv.extend(["--fund-code", args.fund_code])
    if args.resolve_env:
        argv.append("--resolve-env")
    if args.json_output:
        argv.append("--json")
    sys.argv = ["provider_smoke"] + argv
    return smoke_main()


def _cmd_audit(args: argparse.Namespace) -> int:
    from scripts.audit.run_all_audits import main as audit_main
    argv = []
    if args.pretty:
        argv.append("--pretty")
    if args.json_output:
        argv.append("--json")
    sys.argv = ["run_all_audits"] + argv
    return audit_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fund-agent",
        description="fund-agent: host-agnostic financial research skill pack CLI",
    )
    sub = parser.add_subparsers(dest="command")

    p_doctor = sub.add_parser("doctor", help="Deterministic readiness check")
    p_doctor.add_argument("--pretty", action="store_true")
    p_doctor.add_argument("--json", dest="json_output", action="store_true")

    p_run = sub.add_parser("run-skill", help="Run a manifest skill via JSON bridge")
    p_run.add_argument("--skill", help="Skill ID (e.g. fund_analysis)")
    p_run.add_argument("--input", dest="input_file", help="Input JSON path")
    p_run.add_argument("--pretty", action="store_true")

    p_reg = sub.add_parser("regressions", help="Run personal portfolio regression fixtures")
    p_reg.add_argument("--pretty", action="store_true")
    p_reg.add_argument("--scenario", help="Run a specific scenario")
    p_reg.add_argument("--show-trace", action="store_true")

    p_smoke = sub.add_parser("provider-smoke", help="Optional host adapter smoke test")
    p_smoke.add_argument("--provider", help="Provider name (e.g. akshare)")
    p_smoke.add_argument("--all", action="store_true", help="Smoke all providers")
    p_smoke.add_argument("--capability", help="Capability to test")
    p_smoke.add_argument("--fund-code", help="Fund code for smoke test")
    p_smoke.add_argument("--resolve-env", action="store_true")
    p_smoke.add_argument("--json", dest="json_output", action="store_true")

    p_audit = sub.add_parser("audit", help="Run project audit scripts")
    p_audit.add_argument("--pretty", action="store_true")
    p_audit.add_argument("--json", dest="json_output", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    dispatch = {
        "doctor": _cmd_doctor,
        "run-skill": _cmd_run_skill,
        "regressions": _cmd_regressions,
        "provider-smoke": _cmd_provider_smoke,
        "audit": _cmd_audit,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
