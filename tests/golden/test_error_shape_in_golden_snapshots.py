"""Golden snapshot error shape guard tests.

Scans all golden snapshot JSON files and asserts that every error
object (in errors[] and top-level error) is canonical shape with
code, message, details (dict), and recoverable (bool).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden.error_shape_assertions import assert_snapshot_file_errors_are_canonical

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIRS = [
    ROOT / "tests" / "golden" / "fund_analysis",
    ROOT / "tests" / "golden" / "decision_support",
    ROOT / "tests" / "golden" / "thesis_generation",
]


def _collect_snapshot_files() -> list[Path]:
    files: list[Path] = []
    for d in GOLDEN_DIRS:
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                files.append(f)
    return files


@pytest.mark.parametrize("snapshot_path", _collect_snapshot_files(), ids=lambda p: p.name)
class TestGoldenSnapshotErrorShape:
    def test_errors_are_canonical(self, snapshot_path: Path):
        assert_snapshot_file_errors_are_canonical(snapshot_path)

    def test_errors_is_list_if_present(self, snapshot_path: Path):
        import json
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        errors = data.get("errors")
        if errors is not None:
            assert isinstance(errors, list), f"errors must be list in {snapshot_path.name}"

    def test_no_string_errors(self, snapshot_path: Path):
        import json
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for err in data.get("errors", []):
            assert isinstance(err, dict), f"string error in {snapshot_path.name}: {err!r}"

    def test_details_is_dict(self, snapshot_path: Path):
        import json
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for err in data.get("errors", []):
            assert isinstance(err.get("details"), dict), f"non-dict details in {snapshot_path.name}: {err!r}"

    def test_recoverable_is_bool(self, snapshot_path: Path):
        import json
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for err in data.get("errors", []):
            assert isinstance(err.get("recoverable"), bool), f"non-bool recoverable in {snapshot_path.name}: {err!r}"
