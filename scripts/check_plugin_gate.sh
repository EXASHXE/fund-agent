#!/usr/bin/env bash
set -euo pipefail

echo "=== compileall ==="
PYTHONPATH=. python -m compileall src tests
echo

echo "=== parser checks ==="
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/plugin-ci.yml'))"
python -c "import yaml; yaml.safe_load(open('skillpack/fund-agent.skillpack.yaml'))"
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
PYTHONPATH=. python scripts/check_examples.py

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

echo "=== install smoke ==="
PYTHONPATH=. pytest tests/integration/test_install_smoke.py -q
echo

echo "=== install ==="
PYTHONPATH=. pytest tests/install -q
echo

echo "=== default gate ==="
PYTHONPATH=. pytest -q
echo

echo "All plugin gate checks passed."
