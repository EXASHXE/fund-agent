from src.routes.cli_router import build_parser, run_cli


def test_cli_router_parses_analyze_flags():
    parser = build_parser()
    args = parser.parse_args([
        "analyze",
        "-c",
        "fund-portfolio.yaml",
        "-o",
        "report.md",
        "--recommend",
        "--stress",
        "--no-snapshot-after",
        "--agent-decisions",
        "agent_decisions.json",
    ])

    assert args.command == "analyze"
    assert args.config == "fund-portfolio.yaml"
    assert args.recommend is True
    assert args.stress is True
    assert args.snapshot_after is False
    assert args.agent_decisions == "agent_decisions.json"


def test_run_cli_dispatches_to_named_handler():
    calls = []

    def handle(args):
        calls.append((args.command, args.output))
        return "ok"

    result = run_cli({"init": handle}, ["init", "-o", "demo.yaml"])

    assert result == "ok"
    assert calls == [("init", "demo.yaml")]
