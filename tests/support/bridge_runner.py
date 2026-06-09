"""Runtime bridge test invocation helpers.

Provides shared helpers for running the runtime bridge CLI as a subprocess
or in-process, parsing JSON output, and writing temporary input files.

These helpers must not import provider SDKs or perform network calls.
They should not mask behavior changes; tests should still assert
explicit semantics.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

from src.skillpack.run_skill import run_bridge


def project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


def run_bridge_subprocess(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the runtime bridge CLI as a subprocess."""
    root = project_root()
    cmd = [sys.executable, str(root / "scripts" / "run_skill.py")] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(root))


def stdout_text(result: subprocess.CompletedProcess) -> str:
    """Extract stdout text from a subprocess result."""
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def parse_stdout_json(result: subprocess.CompletedProcess) -> dict:
    """Parse stdout JSON from a subprocess result."""
    return json.loads(stdout_text(result))


def write_temp_json(data: dict) -> Path:
    """Write data to a temporary JSON file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.flush()
    f.close()
    return Path(f.name)


def run_bridge_inprocess_json(
    *,
    skill: str,
    input_data: dict | None = None,
    input_text: str | None = None,
    emit_report: str | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    """Run the runtime bridge in-process and return the parsed JSON output."""
    if input_text is None and input_data is not None:
        input_text = json.dumps(input_data)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        if input_text:
            f.write(input_text)
        f.flush()
        path = f.name

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=path, input_text=input_text, emit_report=emit_report)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return json.loads(output.strip())
