"""Release-freeze gate tests — only run during release validation."""

import pytest

pytestmark = [
    pytest.mark.release,
]
