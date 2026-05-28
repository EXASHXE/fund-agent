"""Thin CLI entrypoint; command handlers live in src.routes.commands."""

import os
import sys

from src.routes.cli_router import run_cli
from src.routes.commands import (
    cmd_analyze as _cmd_analyze,
    cmd_diagnose,
    cmd_fetch,
    cmd_import,
    cmd_init,
    cmd_news,
    cmd_recommend,
    cmd_score,
    cmd_snapshot,
    cmd_ui,
    command_handlers,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    pd.options.mode.string_storage = "python"
except ImportError:
    pass


def request_agent_keywords_inline(
    holding_codes: list,
    fund_profiles: list,
) -> dict | None:
    """Runtime hook for an embedding agent to provide news keywords inline."""
    return None


def cmd_analyze(args):
    """Run the core analyze workflow."""
    return _cmd_analyze(args, keyword_callback=request_agent_keywords_inline)


def main(argv=None):
    handlers = command_handlers(keyword_callback=request_agent_keywords_inline)
    handlers["analyze"] = cmd_analyze
    return run_cli(handlers, argv=argv)


if __name__ == "__main__":
    main()
