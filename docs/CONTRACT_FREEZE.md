# Contract Freeze — v0.4.0.dev0

This document lists contracts that are frozen at `rc-stable` for
`skillpack.v1`. Breaking changes require a `schema_version` bump.

## Frozen Contracts

### 1. SkillInput / SkillOutput

- **Location:** `src/schemas/skill.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional fields with defaults, add new error codes
- **Breaking:** renaming/removing required fields, changing field types

### 2. SkillError

- **Location:** `src/schemas/skill.py`
- **Stability:** rc-stable
- **Allowed changes:** add new standard error codes, add optional details fields
- **Breaking:** removing existing error codes, changing `recoverable` semantics

### 3. EvidenceItem

- **Location:** `src/schemas/evidence.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional metadata fields
- **Breaking:** changing `confidence_weight` range, removing `source_type`

### 4. EvidenceGraph

- **Location:** `src/schemas/evidence_graph.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional graph metadata
- **Breaking:** changing node/edge schemas, removing `to_dict()` contract

### 5. EvidenceGraphCompileResult / EvidenceGraphCompileReport

- **Location:** `src/tools/evidence/validators.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional report fields
- **Breaking:** removing `graph` or `report` from result

### 6. Decision

- **Location:** `src/schemas/decision.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional audit trail entries
- **Breaking:** changing action enum values, removing `rationale_anchor`

### 7. ExecutionLedger

- **Location:** `src/schemas/decision.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional ledger metadata
- **Breaking:** changing `decisions` list schema

### 8. MCPCapability / MCPHostAdapter

- **Location:** `src/tools/adapters/mcp.py`
- **Stability:** rc-stable
- **Allowed changes:** add optional adapter methods
- **Breaking:** changing `call()` or `list_capabilities()` signatures

### 9. Fund And Portfolio Schemas

- **Location:** `src/schemas/fund.py`
- **Stability:** dev-stable
- **Allowed changes:** add optional fields with defaults, add new report sections
- **Breaking:** removing required fund/portfolio fields, changing `to_dict()` shape

### 10. Skillpack Manifest

- **Location:** `skillpack/fund-agent.skillpack.yaml`
- **Schema version:** `skillpack.v1`
- **Stability:** rc-stable
- **Allowed changes:** add new skills, tools, or optional fields
- **Breaking:** removing required skills, changing `package_role` or `orchestration_owner`

### 11. Tool Catalog

- **Location:** `skillpack/tools.yaml`
- **Stability:** rc-stable
- **Allowed changes:** add new tools, add optional fields
- **Breaking:** removing required fields (`id`, `import_path`, `category`)

### 12. Report Output Contract

- **Location:** `docs/contracts/report-output-contract.v1.md`
- **Stability:** dev-stable
- **Allowed changes:** add optional section fields, append optional sections
- **Breaking:** removing or reordering existing sections, changing status semantics

### 13. Fund Analysis Input Contract

- **Location:** `docs/contracts/fund-analysis-input-contract.v1.md`
- **Machine-readable:** `skillpack/input-contracts.yaml`
- **Stability:** dev-stable
- **Allowed changes:** add optional input fields, add optional metadata fields
- **Breaking:** removing or renaming existing contract fields, changing minimum input mode semantics

### 14. Fund Analysis Artifact Contract

- **Location:** `docs/contracts/fund-analysis-artifacts.v1.md`
- **Machine-readable:** `skillpack/artifact-contracts.yaml`
- **Stability:** dev-stable
- **Allowed changes:** add optional artifact keys, add optional metadata fields
- **Breaking:** removing or renaming existing contract keys, changing core artifact semantics

## Versioning Policy

- `v0.x.y` — pre-1.0, minor breaking changes allowed with notice
- `v1.0.0` — stable API, full backward compatibility
- `skillpack.v1` — manifest schema, frozen for the host-agnostic plugin contract
