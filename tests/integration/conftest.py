"""Integration tests — multi-module, may be slower than unit tests."""

import pytest

pytestmark = [
    pytest.mark.integration,
]
