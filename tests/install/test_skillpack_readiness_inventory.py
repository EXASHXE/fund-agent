"""Host-facing source checkout readiness inventory tests."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_HOST_FILES = (
    "README.md",
    "docs/START_HERE.md",
    "docs/install/runtime-bridge-cli.md",
    "docs/host-integrations/README.md",
    "opencode.plugin.js",
    "package.json",
    "pyproject.toml",
    "scripts/run_skill.py",
    "skillpack/fund-agent.skillpack.yaml",
    "skillpack/capabilities.yaml",
    "skillpack/tools.yaml",
    "skillpack/input-contracts.yaml",
    "skillpack/artifact-contracts.yaml",
    "skillpack/decision-contracts.yaml",
    "skillpack/thesis-contracts.yaml",
    "docs/contracts/fund-analysis-input-contract.v1.md",
    "docs/contracts/fund-analysis-artifacts.v1.md",
    "docs/contracts/decision-support-contract.v1.md",
    "docs/contracts/thesis-generation-contract.v1.md",
    "docs/contracts/report-output-contract.v1.md",
    "docs/contracts/skill-output-contract.v1.md",
    "examples/scenarios/README.md",
    "examples/decision_support/README.md",
    "examples/thesis_generation/README.md",
    "tests/golden/README.md",
)

CONTRACT_YAML_FILES = (
    "skillpack/capabilities.yaml",
    "skillpack/tools.yaml",
    "skillpack/input-contracts.yaml",
    "skillpack/artifact-contracts.yaml",
    "skillpack/decision-contracts.yaml",
    "skillpack/thesis-contracts.yaml",
)


def test_required_host_facing_files_exist_and_are_utf8_readable() -> None:
    for relpath in REQUIRED_HOST_FILES:
        path = ROOT / relpath
        assert path.exists(), f"missing required host-facing file: {relpath}"
        path.read_text(encoding="utf-8")
        assert "docs/archive" not in relpath
        assert "fund-analyst" not in relpath


def test_required_yaml_and_json_files_parse() -> None:
    yaml_paths = ["skillpack/fund-agent.skillpack.yaml", *CONTRACT_YAML_FILES]
    for relpath in yaml_paths:
        parsed = yaml.safe_load((ROOT / relpath).read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), f"{relpath} must parse to a YAML mapping"

    for directory in (
        ROOT / "examples" / "scenarios",
        ROOT / "examples" / "decision_support",
        ROOT / "examples" / "thesis_generation",
    ):
        for path in sorted(directory.glob("*.json")):
            parsed = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(parsed, dict), f"{path} must parse to a JSON object"


def test_package_metadata_references_source_checkout_runtime_bridge_path() -> None:
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    bridge = package_json["fundAgent"]["runtimeBridge"]

    assert bridge["path"] == "scripts/run_skill.py"
    assert bridge["distribution"] == "source-checkout-only"
    assert (ROOT / bridge["path"]).is_file()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == ">=3.11"


def test_all_manifest_runtime_paths_import() -> None:
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )

    for skill in manifest["skills"]:
        module_name, attr_name = skill["runtime"].split(":", 1)
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), (
            f"{skill['name']} runtime {skill['runtime']} does not import"
        )


def test_all_manifest_skill_docs_exist() -> None:
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )

    for skill in manifest["skills"]:
        slug = skill["name"].replace("_", "-")
        path = ROOT / "skills" / slug / "SKILL.md"
        assert path.is_file(), f"missing skill doc for {skill['name']}: {path}"


def test_all_manifest_contract_docs_exist() -> None:
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )

    for relpath in manifest["contracts"]:
        assert (ROOT / relpath).is_file(), f"manifest contract missing: {relpath}"


def test_deprecated_runtime_surfaces_and_legacy_slug_are_not_discoverable() -> None:
    manifest_text = (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(
        encoding="utf-8"
    )
    assert "fund-analyst" not in manifest_text
    assert not (ROOT / "skills" / "fund-analyst").exists()

    for relpath in (
        "src/core",
        "src/infra",
        "src/workflows",
        "src/config",
        "src/data",
        "src/db",
        "src/kg",
        "src/vectorstore",
        "src/cli.py",
    ):
        assert not (ROOT / relpath).exists(), f"deprecated source surface returned: {relpath}"
