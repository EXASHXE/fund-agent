#!/usr/bin/env bash
# test_identity_nav.sh — Identity/NAV/reconstruction main path verification
# Run after changes to identity resolution, NAV, or reconstruction.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== identity/NAV/reconstruction tests ==="
PYTHONPATH=. python -m pytest -q tests/end_to_end/test_e2e_identity_nav.py

echo
echo "Identity/NAV gate passed."
