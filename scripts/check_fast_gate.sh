#!/usr/bin/env bash
set -euo pipefail

echo "=== fast gate (excluding slow/subprocess/install markers) ==="
PYTHONPATH=. python -m pytest -q -m "not slow and not subprocess and not install and not windows_slow" --ignore=tests/ci
echo
echo "Fast gate passed."
