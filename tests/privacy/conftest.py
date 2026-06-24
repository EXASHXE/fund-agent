"""Privacy / artifact safety checks — release gate level."""

import pytest

pytestmark = [
    pytest.mark.privacy,
    pytest.mark.release,
]
