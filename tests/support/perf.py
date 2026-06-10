"""Shared performance and test session helpers.

Provides platform detection, timeout configuration, and file I/O
caching for deterministic test infrastructure.

Timeouts are controlled by environment variables:
- FUND_AGENT_TEST_SUBPROCESS_TIMEOUT (default 20)
- FUND_AGENT_TEST_SLOW_TIMEOUT (default 60)
- FUND_AGENT_RUN_SLOW_TESTS (default 1)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any


def is_windows() -> bool:
    return platform.system() == "Windows"


def default_subprocess_timeout() -> int:
    return int(os.environ.get("FUND_AGENT_TEST_SUBPROCESS_TIMEOUT", "20"))


def default_slow_timeout() -> int:
    return int(os.environ.get("FUND_AGENT_TEST_SLOW_TIMEOUT", "60"))


def should_run_slow_tests() -> bool:
    return os.environ.get("FUND_AGENT_RUN_SLOW_TESTS", "1") != "0"


def maybe_skip_if_missing_executable(executable: str) -> None:
    if shutil.which(executable) is None:
        import pytest
        pytest.skip(f"{executable} not available on test host")


@lru_cache(maxsize=256)
def stable_json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=256)
def stable_text_read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=64)
def stable_yaml_load(path: Path) -> dict[str, Any]:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))
