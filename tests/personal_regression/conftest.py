"""Personal regression tests — not part of fast gate."""

import pytest

pytestmark = [
    pytest.mark.regression,
    pytest.mark.slow,
]
