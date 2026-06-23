#!/usr/bin/env bash
# test_changed.sh — Run tests relevant to changed files (git diff based)
# Quick feedback loop during development. Not a substitute for test_fast.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHANGED=$(git diff --name-only HEAD 2>/dev/null || true)
STAGED=$(git diff --cached --name-only 2>/dev/null || true)
ALL_CHANGED="${CHANGED} ${STAGED}"

echo "=== Changed files ==="
echo "$ALL_CHANGED" | tr ' ' '\n' | grep -v '^$' | sort -u
echo

# Always run ruff on changed Python files
PY_CHANGED=$(echo "$ALL_CHANGED" | tr ' ' '\n' | grep '\.py$' | grep -v '^$' | sort -u || true)
if [ -n "$PY_CHANGED" ]; then
    echo "=== ruff check (changed files) ==="
    python -m ruff check $PY_CHANGED 2>/dev/null || true
    echo "  Done"
fi

# Identity/NAV core scripts
IDENTITY_FILES="scripts/resolve_fund_identities.py scripts/reconstruct_portfolio_from_ledger.py scripts/fund_agent_e2e.py scripts/fund_identity_utils.py"
for f in $IDENTITY_FILES; do
    if echo "$ALL_CHANGED" | grep -q "$(basename $f)"; then
        echo "=== identity/NAV tests (changed: $f) ==="
        bash scripts/test_identity_nav.sh
        break
    fi
done

# Plugin/wrapper/skill changes
PLUGIN_DIRS="src/skills_runtime src/skillpack skills/ skillpack/ tests/agent_wrappers tests/skillpack"
for d in $PLUGIN_DIRS; do
    if echo "$ALL_CHANGED" | grep -q "$d"; then
        echo "=== plugin smoke (changed: $d) ==="
        bash scripts/test_plugin_smoke.sh
        break
    fi
done

# Privacy-related changes
if echo "$ALL_CHANGED" | grep -qE "(privacy|secret|leak)"; then
    echo "=== privacy check ==="
    bash bin/fund-agent-privacy-check
fi

# Schema/contract changes
if echo "$ALL_CHANGED" | grep -qE "(schemas|contracts|src/schemas)"; then
    echo "=== schema + contract tests ==="
    PYTHONPATH=. python -m pytest -q tests/schemas tests/contracts -m "not slow"
fi

# Tools/portfolio changes
if echo "$ALL_CHANGED" | grep -qE "(src/tools|tests/tools)"; then
    echo "=== tools/portfolio tests ==="
    PYTHONPATH=. python -m pytest -q tests/tools/portfolio -m "not slow"
fi

echo
echo "Changed-file tests done. Run test_fast.sh for broader coverage."
