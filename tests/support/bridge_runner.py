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


def run_bridge_subprocess(args: list[str], *, timeout: int = 60, input: str | None = None) -> subprocess.CompletedProcess:
    """Run the runtime bridge CLI as a text subprocess."""
    return subprocess.run(
        [sys.executable, str(BRIDGE_SCRIPT), *args],
        cwd=str(ROOT),
        env=bridge_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input,
        timeout=timeout,
    )


run_bridge = run_bridge_subprocess


def stdout_text(result: subprocess.CompletedProcess) -> str:
    """Extract stdout text from a subprocess result."""
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def parse_stdout_json(result: subprocess.CompletedProcess) -> dict:
    """Parse stdout JSON from a subprocess result."""
    text = stdout_text(result)
    assert text.strip(), (
        f"stdout must contain JSON, rc={result.returncode}, stderr={result.stderr!r}"
    )
    return json.loads(text)


def parse_json_stdout(proc: subprocess.CompletedProcess) -> dict[str, Any]:
    """Compatibility alias for parse_stdout_json."""
    return parse_stdout_json(proc)


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


def run_bridge_inprocess_text(
    *,
    skill: str,
    input_data: dict | None = None,
    input_text: str | None = None,
    emit_report: str | None = None,
) -> str:
    """Run the runtime bridge in-process and return raw stdout text."""
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

    return output


def run_bridge_inprocess_metadata(
    *,
    list_skills: bool = False,
    list_capabilities: bool = False,
    describe_capability: str | None = None,
    skill: str | None = None,
    explain_input: bool = False,
    validate_input: bool = False,
    output_schema: bool = False,
    input_data: dict | None = None,
    input_text: str | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    """Run a metadata bridge command in-process and return parsed JSON output.

    Supports --list-skills, --list-capabilities, --describe-capability,
    --explain-input, --validate-input, and --output-schema.
    """
    if input_text is None and input_data is not None:
        input_text = json.dumps(input_data)

    input_path: str | None = None
    if input_text is not None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(input_text)
            f.flush()
            input_path = f.name

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        run_bridge_inprocess(
            skill_name=skill,
            input_path=input_path,
            input_text=input_text,
            pretty=pretty,
            list_skills=list_skills,
            list_capabilities=list_capabilities,
            describe_capability=describe_capability,
            explain_input=explain_input,
            validate_input=validate_input,
            output_schema=output_schema,
        )
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return json.loads(output.strip())
