#!/usr/bin/env bash
# test_release_gate.sh — Full release-freeze gate
# Run before tagging a release. Includes everything.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== ruff check (canonical release scope) ==="
bash scripts/lint_release_scope.sh

echo "=== compileall ==="
PYTHONPATH=. python -m compileall src tests scripts -q 2>/dev/null
echo "  OK"

echo "=== privacy check ==="
bash bin/fund-agent-privacy-check
echo "  OK"

echo "=== plugin gate ==="
bash scripts/check_plugin_gate.sh
echo "  OK"

echo "=== full pytest ==="
PYTHONPATH=. python -m pytest -q
echo "  OK"

echo "=== check examples ==="
PYTHONPATH=. python scripts/check_examples.py
echo "  OK"

echo
echo "Release gate passed."
