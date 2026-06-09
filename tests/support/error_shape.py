"""Canonical host-visible error shape assertion helpers.

Provides shared assertion functions for verifying that error objects
in host-visible output follow the canonical shape:

    {
        "code": string (non-empty),
        "message": string (non-empty),
        "details": dict,
        "recoverable": bool,
    }

These helpers must not import provider SDKs or perform network calls.
They should not mask behavior changes; tests should still assert
explicit semantics.
"""

from __future__ import annotations

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


def assert_bridge_error_shape(error: dict[str, Any]) -> None:
    """Assert that a runtime bridge top-level error is canonical."""
    assert_canonical_error(error)


def assert_skill_error_shape(error: dict[str, Any]) -> None:
    """Assert that a SkillOutput error is canonical."""
    assert_canonical_error(error)


def assert_skill_errors_canonical(errors: list[dict[str, Any]]) -> None:
    """Assert that all SkillOutput errors are canonical."""
    for error in errors:
        assert_skill_error_shape(error)


def assert_envelope_errors_are_canonical(envelope: dict[str, Any]) -> None:
    """Assert that all errors in an envelope's errors[] list are canonical shape."""
    errors = envelope.get("errors")
    if errors is None:
        return
    assert isinstance(errors, list), f"errors must be list, got {type(errors).__name__}"
    for err in errors:
        assert_canonical_error(err)


def assert_top_level_error_is_canonical(envelope: dict[str, Any]) -> None:
    """Assert that the top-level 'error' key in an envelope is canonical shape, if present."""
    if "error" in envelope:
        assert_canonical_error(envelope["error"])


def assert_all_errors_are_canonical(envelope: dict[str, Any]) -> None:
    """Assert that both errors[] and top-level error are canonical shape."""
    assert_envelope_errors_are_canonical(envelope)
    assert_top_level_error_is_canonical(envelope)
