#!/usr/bin/env bash
# test_ci.sh — Reproduce GitHub CI test semantics locally
# Mirrors what ci.yml runs: lint scope + pytest with coverage.
# For release-level gate, use: bash scripts/test_release_gate.sh
# For fast dev iteration, use: bash scripts/test_fast.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== release lint scope ==="
bash scripts/lint_release_scope.sh

echo "=== pytest with coverage ==="
PYTHONPATH=. python -m pytest --cov=src -q

echo
echo "CI gate passed."
