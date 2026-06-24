#!/usr/bin/env bash
# test_release_gate.sh — Full release-freeze gate
# Run before tagging a release. Includes everything.
# Uses --cov=src to match CI semantics.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== CI gate (lint + coverage) ==="
bash scripts/test_ci.sh
echo "  OK"

echo "=== privacy check ==="
bash bin/fund-agent-privacy-check
echo "  OK"

echo "=== plugin gate ==="
bash scripts/check_plugin_gate.sh
echo "  OK"

echo "=== check examples ==="
PYTHONPATH=. python scripts/check_examples.py
echo "  OK"

echo
echo "Release gate passed."
