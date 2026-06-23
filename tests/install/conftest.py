"""Install tests are slow subprocess-level tests — excluded from fast gate."""

import pytest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.subprocess,
    pytest.mark.install,
]
