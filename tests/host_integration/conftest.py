"""Host integration tests — subprocess-heavy, excluded from fast gate."""

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.subprocess,
]
