#!/usr/bin/env bash
# check_plugin_gate_fast.sh — Fast plugin gate (development)
# Quick smoke check for plugin/wrapper/contract integrity.
# For full gate, use: bash scripts/check_plugin_gate.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== compileall ==="
PYTHONPATH=. python -m compileall src tests -q 2>/dev/null
echo

echo "=== architecture ==="
PYTHONPATH=. python -m pytest tests/architecture -q
echo

echo "=== contracts ==="
PYTHONPATH=. python -m pytest tests/contracts -q
echo

echo "=== skillpack ==="
PYTHONPATH=. python -m pytest tests/skillpack -q
echo

echo "=== skills ==="
PYTHONPATH=. python -m pytest tests/skills -q
echo

echo "=== tools ==="
PYTHONPATH=. python -m pytest tests/tools -q
echo

echo "Fast plugin gate passed. For full gate: bash scripts/check_plugin_gate.sh"
