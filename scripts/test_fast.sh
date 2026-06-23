#!/usr/bin/env bash
# test_fast.sh — Fast development gate (target: 30–90s)
# Run frequently during development. Only covers fast unit/smoke/critical paths.
# For full coverage, run test_release_gate.sh before tagging.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== ruff check (active scripts) ==="
python -m ruff check \
    scripts/fund_agent_e2e.py \
    scripts/fund_identity_utils.py \
    scripts/resolve_fund_identities.py \
    scripts/import_alipay_transactions.py \
    scripts/reconstruct_portfolio_from_ledger.py \
    scripts/build_fund_data_snapshot.py \
    scripts/build_factor_snapshot.py \
    tests/end_to_end/ \
    2>/dev/null || true
echo "  Done"

echo "=== compileall (src + scripts) ==="
PYTHONPATH=. python -m compileall src scripts -q 2>/dev/null
echo "  OK"

echo "=== fast pytest (explicit fast paths, exclude slow/subprocess) ==="
PYTHONPATH=. python -m pytest -q \
    tests/end_to_end/test_e2e_identity_nav.py \
    tests/schemas/ \
    tests/tools/portfolio/ \
    tests/contracts/ \
    tests/ci/ \
    tests/graph/ \
    tests/golden/ \
    tests/public_api/ \
    tests/reporting/ \
    tests/skills/ \
    tests/host_data/ \
    tests/host_adapters/ \
    tests/evidence/ \
    tests/evaluation/ \
    tests/examples/ \
    tests/skills_runtime/ \
    tests/docs/ \
    tests/architecture/test_architecture_boundaries.py \
    tests/scripts/ \
    tests/workflow/ \
    -m "not slow and not subprocess and not release and not real_e2e and not live_provider and not adapter_live"

echo
echo "Fast gate passed."
