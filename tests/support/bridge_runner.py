"""Runtime bridge test invocation helpers.

Provides shared helpers for running the runtime bridge CLI as a subprocess
or in-process, parsing JSON output, and writing temporary input files.

These helpers must not import provider SDKs or perform network calls.
They should not mask behavior changes; tests should still assert
explicit semantics.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

from src.skillpack.run_skill import run_bridge as run_bridge_inprocess

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = ROOT / "scripts" / "run_skill.py"


def project_root() -> Path:
    """Return the repository root directory."""
    return ROOT


def bridge_env() -> dict[str, str]:
    """Return an environment suitable for source-checkout bridge execution."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return env


def run_bridge(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the runtime bridge CLI as a text subprocess."""
    return subprocess.run(
        [sys.executable, str(BRIDGE_SCRIPT), *args],
        cwd=str(ROOT),
        env=bridge_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_bridge_subprocess(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the runtime bridge CLI as a subprocess."""
    return run_bridge(args, timeout=timeout)


def stdout_text(result: subprocess.CompletedProcess) -> str:
    """Extract stdout text from a subprocess result."""
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def parse_stdout_json(result: subprocess.CompletedProcess) -> dict:
    """Parse stdout JSON from a subprocess result."""
    return json.loads(stdout_text(result))


def parse_json_stdout(proc: subprocess.CompletedProcess) -> dict[str, Any]:
    """Parse stdout JSON, preserving stderr in assertion messages."""
    assert proc.stdout.strip(), (
        f"stdout must contain JSON, rc={proc.returncode}, stderr={proc.stderr!r}"
    )
    return json.loads(proc.stdout)


def run_bridge_json(args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    """Run the runtime bridge CLI and parse stdout JSON."""
    return parse_json_stdout(run_bridge(args, timeout=timeout))


def write_temp_json(
    tmp_path_or_payload: Path | Any,
    payload: Any | None = None,
    name: str = "input.json",
) -> Path:
    """Write JSON either under pytest tmp_path or to a named temporary file."""
    if isinstance(tmp_path_or_payload, Path):
        path = tmp_path_or_payload / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(tmp_path_or_payload, f)
    f.flush()
    f.close()
    return Path(f.name)


def write_temp_text(tmp_path: Path, text: str, name: str = "input.json") -> Path:
    """Write raw text under pytest tmp_path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


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
        run_bridge_inprocess(skill_name=skill, input_path=path, input_text=input_text, emit_report=emit_report)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return json.loads(output.strip())
