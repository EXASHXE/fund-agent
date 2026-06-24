#!/usr/bin/env bash
# profile_tests.sh — Test duration profiling
# Shows slowest tests to identify optimization targets.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHONPATH=. python -m pytest -q --durations=50 "$@"
