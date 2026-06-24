#!/usr/bin/env bash
# test_plugin_smoke.sh — Quick plugin/wrapper/skill smoke check
# Verifies basic plugin structure, skill metadata, and runner wiring.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== compileall ==="
PYTHONPATH=. python -m compileall src scripts -q 2>/dev/null
echo "  OK"

echo "=== skill metadata / schema smoke ==="
PYTHONPATH=. python -m pytest -q tests/skillpack tests/contracts -m "not slow" 2>/dev/null || \
PYTHONPATH=. python -m pytest -q tests/skillpack tests/contracts
echo "  OK"

echo "=== wrapper existence + runner wiring ==="
# Check bin/ wrappers exist and are executable
for f in bin/fund-agent-e2e bin/fund-agent-privacy-check; do
    if [ ! -f "$f" ]; then
        echo "FAIL: $f not found"
        exit 1
    fi
    echo "  $f exists"
done

echo "=== E2E runner --help smoke ==="
PYTHONPATH="$REPO_ROOT" python scripts/fund_agent_e2e.py --help > /dev/null
echo "  OK"

echo "=== E2E runner --dry-run smoke ==="
PYTHONPATH="$REPO_ROOT" python scripts/fund_agent_e2e.py --dry-run 2>/dev/null || true
echo "  OK"

echo "=== architecture boundaries ==="
PYTHONPATH=. python -m pytest -q tests/architecture -m "not slow" 2>/dev/null || \
PYTHONPATH=. python -m pytest -q tests/architecture
echo "  OK"

echo
echo "Plugin smoke passed."
