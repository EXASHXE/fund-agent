import sys
import os
import shutil
import subprocess

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_examples_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
if _examples_dir not in sys.path:
    sys.path.insert(0, _examples_dir)


def _has_node() -> bool:
    for candidate in ("node", "bun"):
        if shutil.which(candidate):
            try:
                subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return True
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
    return False


NODE_AVAILABLE = _has_node()


@pytest.fixture(scope="session")
def node_check_opencode_plugin():
    """Run node --check on opencode.plugin.js once per session.
    Returns True if check passed, None if node unavailable."""
    if not NODE_AVAILABLE:
        return None
    from pathlib import Path
    plugin = Path(__file__).resolve().parents[1] / "opencode.plugin.js"
    result = subprocess.run(
        ["node", "--check", str(plugin)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0
