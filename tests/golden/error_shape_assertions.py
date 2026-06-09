"""Golden snapshot error shape assertion helpers.

Re-exports canonical error shape assertions from the shared
tests.support.error_shape module and adds golden-snapshot-specific
helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.support.error_shape import (
    assert_all_errors_are_canonical as assert_envelope_errors_are_canonical,
    assert_canonical_error,
)


def assert_snapshot_file_errors_are_canonical(path: Path) -> None:
    """Assert that all errors in a snapshot JSON file are canonical shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"snapshot must be a JSON object: {path}"
    assert_envelope_errors_are_canonical(data)
