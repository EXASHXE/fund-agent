#!/usr/bin/env bash
# lint_release_scope.sh — Canonical v0.10.5 release lint scope
# Only checks files in the critical runtime path. Full-project ruff is NOT a
# release blocker in v0.10.5 (590 historical lint issues exist).
# New/modified files MUST be ruff-clean within this scope.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== ruff check (canonical release scope) ==="
python -m ruff check \
    scripts/fund_agent_e2e.py \
    scripts/import_alipay_transactions.py \
    scripts/resolve_fund_identities.py \
    scripts/reconstruct_portfolio_from_ledger.py \
    scripts/fund_identity_utils.py \
    scripts/build_fund_data_snapshot.py \
    scripts/build_factor_snapshot.py \
    scripts/privacy_audit.py \
    src/skills_runtime/ \
    src/schemas/ \
    src/tools/portfolio/ \
    src/tools/workflow/ \
    src/tools/adapters/ \
    src/tools/evidence/ \
    src/fund_agent/ \
    tests/end_to_end/test_e2e_identity_nav.py \
    tests/tools/portfolio/ \
    tests/scripts/ \
    tests/schemas/ \
    tests/contracts/ \
    tests/skills_runtime/ \
    tests/architecture/

echo "  OK"
echo
echo "Release lint scope passed. Note: ruff check . is NOT a v0.10.5 release blocker."
echo "Full-project lint debt is tracked for v0.10.6."
