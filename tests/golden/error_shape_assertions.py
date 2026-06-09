"""Golden snapshot error shape assertion helpers.

Provides helpers to verify that golden snapshot files contain only
canonical error objects with code, message, details (dict), and
recoverable (bool) fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def assert_canonical_error(error: object) -> None:
    """Assert that a single error object is canonical shape."""
    assert isinstance(error, dict), f"error must be dict, got {type(error).__name__}: {error!r}"
    assert "code" in error, f"error missing 'code': {error}"
    assert "message" in error, f"error missing 'message': {error}"
    assert "details" in error, f"error missing 'details': {error}"
    assert "recoverable" in error, f"error missing 'recoverable': {error}"
    assert isinstance(error["code"], str) and len(error["code"]) > 0, (
        f"code must be non-empty str: {error['code']!r}"
    )
    assert isinstance(error["message"], str) and len(error["message"]) > 0, (
        f"message must be non-empty str: {error['message']!r}"
    )
    assert isinstance(error["details"], dict), (
        f"details must be dict, got {type(error['details']).__name__}: {error['details']!r}"
    )
    assert isinstance(error["recoverable"], bool), (
        f"recoverable must be bool, got {type(error['recoverable']).__name__}: {error['recoverable']!r}"
    )


def assert_envelope_errors_are_canonical(envelope: dict[str, Any]) -> None:
    """Assert that all errors in an envelope are canonical shape."""
    errors = envelope.get("errors")
    if errors is None:
        return
    assert isinstance(errors, list), f"errors must be list, got {type(errors).__name__}"
    for err in errors:
        assert_canonical_error(err)

    top_error = envelope.get("error")
    if top_error is not None:
        assert_canonical_error(top_error)


def assert_snapshot_file_errors_are_canonical(path: Path) -> None:
    """Assert that all errors in a snapshot JSON file are canonical shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"snapshot must be a JSON object: {path}"
    assert_envelope_errors_are_canonical(data)
