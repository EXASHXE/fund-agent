"""Validation helpers for skill pack manifests."""

from __future__ import annotations

import importlib
from pathlib import Path

from src.skillpack.manifest import SkillPackManifest

REQUIRED_TOP_LEVEL = {
    "name",
    "version",
    "type",
    "description",
    "skills",
    "tools",
    "schemas",
    "contracts",
    "mcp_capabilities",
    "host_integration",
    "forbidden_behaviors",
}


def validate_manifest(manifest: SkillPackManifest) -> list[str]:
    """Validate manifest shape and importable runtime/schema paths."""
    errors: list[str] = []

    if manifest.type != "host-agnostic-financial-research-skill-pack":
        errors.append("Manifest type must be host-agnostic-financial-research-skill-pack")
    if not manifest.skills:
        errors.append("Manifest must declare at least one skill")
    if _references_research_os_required_entrypoint(manifest):
        errors.append("ResearchOS must not be a required host integration entrypoint")

    declared_capabilities = {
        item.get("name")
        for item in manifest.mcp_capabilities
        if isinstance(item, dict)
    }
    for skill in manifest.skills:
        for label, path in (
            ("runtime", skill.runtime),
            ("input_schema", skill.input_schema),
            ("output_schema", skill.output_schema),
        ):
            if not _can_resolve(path):
                errors.append(f"Cannot resolve {label} path for {skill.name}: {path}")
        missing = [
            capability
            for capability in skill.requires_mcp
            if capability not in declared_capabilities
        ]
        if missing:
            errors.append(
                f"Skill {skill.name} requires undeclared MCP capabilities: {missing}"
            )

    for contract in manifest.contracts:
        if isinstance(contract, str) and contract.endswith(".md") and not Path(contract).exists():
            errors.append(f"Contract document not found: {contract}")

    if errors:
        raise ValueError("; ".join(errors))
    return []


def _can_resolve(path: str) -> bool:
    if ":" not in path:
        return False
    module_name, attr_name = path.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        value = module
        for part in attr_name.split("."):
            value = getattr(value, part)
    except Exception:
        return False
    return value is not None


def _references_research_os_required_entrypoint(manifest: SkillPackManifest) -> bool:
    host = manifest.host_integration or {}
    required = str(host.get("required_entrypoint", ""))
    if "src.core.research_os" in required or "src/workflows/research_os.py" in required:
        return True
    return any(
        "src.core.research_os" in str(item)
        for item in manifest.tools + manifest.schemas
    )
