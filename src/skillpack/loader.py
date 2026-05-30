"""Load and resolve host-agnostic fund-agent skill pack manifests."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

from src.skillpack.manifest import SkillPackManifest
from src.skillpack.validator import validate_manifest

DEFAULT_MANIFEST_PATH = Path("skillpack/fund-agent.skillpack.yaml")


def load_skillpack_manifest(
    path: str | Path = DEFAULT_MANIFEST_PATH,
    validate: bool = True,
) -> SkillPackManifest:
    """Load a skill pack manifest from YAML."""
    manifest_path = Path(path)
    data = yaml.safe_load(manifest_path.read_text()) or {}
    manifest = SkillPackManifest.from_dict(data)
    if validate:
        validate_manifest(manifest)
    return manifest


def resolve_runtime(runtime_path: str) -> Any:
    """Resolve ``module:attribute`` runtime paths from the manifest."""
    if ":" not in runtime_path:
        raise ValueError(f"Runtime path must use module:attribute form: {runtime_path}")
    module_name, attr_name = runtime_path.split(":", 1)
    module = importlib.import_module(module_name)
    value = module
    for part in attr_name.split("."):
        value = getattr(value, part)
    return value
