"""Validation helpers for skill pack manifests."""

from __future__ import annotations

import importlib
from pathlib import Path

from src.skillpack.manifest import SkillPackManifest
from src.skillpack.resources import resolve_resource_path

REQUIRED_TOP_LEVEL = {
    "name",
    "version",
    "schema_version",
    "package_role",
    "type",
    "description",
    "orchestration_owner",
    "mcp_provider_owner",
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
    if manifest.schema_version != "skillpack.v1":
        errors.append("Manifest schema_version must be skillpack.v1")
    if manifest.package_role != "agent_plugin":
        errors.append("Manifest package_role must be agent_plugin")
    if manifest.orchestration_owner != "external_agent":
        errors.append("Manifest orchestration_owner must be external_agent")
    if manifest.mcp_provider_owner != "external_host":
        errors.append("Manifest mcp_provider_owner must be external_host")
    if manifest.host_integration.get("orchestration_owner") != "external_agent":
        errors.append("host_integration.orchestration_owner must be external_agent")
    if manifest.host_integration.get("planner_owner") != "external_agent":
        errors.append("host_integration.planner_owner must be external_agent")
    if manifest.host_integration.get("mcp_provider_owner") != "external_host":
        errors.append("host_integration.mcp_provider_owner must be external_host")
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
        if isinstance(contract, str) and contract.endswith(".md") and not resolve_resource_path(contract).exists():
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
