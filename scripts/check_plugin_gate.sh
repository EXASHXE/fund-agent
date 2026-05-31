#!/usr/bin/env bash
set -euo pipefail

echo "=== compileall ==="
PYTHONPATH=. python -m compileall src tests
echo

echo "=== architecture ==="
PYTHONPATH=. pytest tests/architecture -q
echo

echo "=== contracts ==="
PYTHONPATH=. pytest tests/contracts -q
echo

echo "=== skillpack ==="
PYTHONPATH=. pytest tests/skillpack -q

echo
echo "=== check examples ==="
python scripts/check_examples.py

echo
echo "=== skills ==="
PYTHONPATH=. pytest tests/skills -q
echo

echo "=== tools ==="
PYTHONPATH=. pytest tests/tools -q
echo

echo "=== integration ==="
PYTHONPATH=. pytest tests/integration -q
echo

echo "=== default gate ==="
PYTHONPATH=. pytest -q
echo

echo "All plugin gate checks passed."
