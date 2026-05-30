"""Typed wrappers for fund-agent skill pack manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillSpec:
    """A single host-callable skill entry from the manifest."""

    name: str
    runtime: str
    input_schema: str
    output_schema: str
    produces: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)
    requires_mcp: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillSpec:
        return cls(
            name=str(data.get("name", "")),
            runtime=str(data.get("runtime", "")),
            input_schema=str(data.get("input_schema", "")),
            output_schema=str(data.get("output_schema", "")),
            produces=list(data.get("produces", [])),
            consumes=list(data.get("consumes", [])),
            requires_mcp=list(data.get("requires_mcp", [])),
            forbidden=list(data.get("forbidden", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runtime": self.runtime,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "produces": self.produces,
            "consumes": self.consumes,
            "requires_mcp": self.requires_mcp,
            "forbidden": self.forbidden,
        }


@dataclass
class SkillPackManifest:
    """Top-level skill pack manifest."""

    name: str
    version: str
    schema_version: str
    package_role: str
    type: str
    description: str
    orchestration_owner: str
    mcp_provider_owner: str
    skills: list[SkillSpec]
    tools: list[str] = field(default_factory=list)
    schemas: list[str] = field(default_factory=list)
    contracts: list[str] = field(default_factory=list)
    mcp_capabilities: list[dict[str, Any]] = field(default_factory=list)
    host_integration: dict[str, Any] = field(default_factory=dict)
    forbidden_behaviors: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillPackManifest:
        return cls(
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            schema_version=str(data.get("schema_version", "")),
            package_role=str(data.get("package_role", "")),
            type=str(data.get("type", "")),
            description=str(data.get("description", "")),
            orchestration_owner=str(data.get("orchestration_owner", "")),
            mcp_provider_owner=str(data.get("mcp_provider_owner", "")),
            skills=[
                SkillSpec.from_dict(item)
                for item in data.get("skills", [])
                if isinstance(item, dict)
            ],
            tools=list(data.get("tools", [])),
            schemas=list(data.get("schemas", [])),
            contracts=list(data.get("contracts", [])),
            mcp_capabilities=list(data.get("mcp_capabilities", [])),
            host_integration=dict(data.get("host_integration", {})),
            forbidden_behaviors=list(data.get("forbidden_behaviors", [])),
        )

    def skill(self, name: str) -> SkillSpec:
        for spec in self.skills:
            if spec.name == name:
                return spec
        raise KeyError(f"Skill '{name}' not found in manifest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "schema_version": self.schema_version,
            "package_role": self.package_role,
            "type": self.type,
            "description": self.description,
            "orchestration_owner": self.orchestration_owner,
            "mcp_provider_owner": self.mcp_provider_owner,
            "skills": [skill.to_dict() for skill in self.skills],
            "tools": self.tools,
            "schemas": self.schemas,
            "contracts": self.contracts,
            "mcp_capabilities": self.mcp_capabilities,
            "host_integration": self.host_integration,
            "forbidden_behaviors": self.forbidden_behaviors,
        }
