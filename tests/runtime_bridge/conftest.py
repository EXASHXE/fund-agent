"""Runtime bridge tests — subprocess-heavy integration tests."""

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.subprocess,
]
