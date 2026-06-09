"""Runtime bridge input introspection and structural validation helpers.

These helpers are intentionally metadata-only. They read the skillpack
manifest and ``capabilities.yaml`` but do not import, instantiate, or run
runtime skill classes. They are meant to help external hosts prepare bridge
inputs, not to validate investment correctness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.skillpack.artifact_contracts import get_skill_artifact_contract
from src.skillpack.decision_contracts import get_decision_contract
from src.skillpack.input_contract_catalog import get_skill_input_contract
from src.skillpack.loader import load_skillpack_manifest
from src.skillpack.manifest import SkillSpec
from src.skillpack.resources import resolve_resource_path
from src.skillpack.thesis_contracts import get_thesis_contract

DEFAULT_MANIFEST_PATH = "skillpack/fund-agent.skillpack.yaml"

STATUS_VALUES = ["OK", "PARTIAL", "FAILED"]

ACTIVE_ACTIONS = ["BUY", "SELL", "INCREASE", "REDUCE"]
PASSIVE_ACTIONS = ["WAIT", "HOLD", "PAUSE_DCA"]


def explain_skill_input(
    skill_id: str,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Return a JSON-serializable host-facing input contract summary."""
    spec, doc_slug = _resolve_skill_spec(skill_id, manifest_path)
    capabilities = _load_capabilities(manifest_path)
    if spec.name == "fund_analysis":
        input_contract = get_skill_input_contract(
            spec.name,
            _input_contract_path_for_manifest(manifest_path),
        )
        contract = _fund_analysis_input_contract(capabilities, input_contract)
    elif spec.name in {"news_research", "sentiment_analysis"}:
        contract = _mcp_skill_input_contract(spec, capabilities)
    elif spec.name == "decision_support":
        contract = _decision_support_input_contract(spec)
    elif spec.name == "thesis_generation":
        contract = _thesis_generation_input_contract(spec)
    else:
        contract = _generic_input_contract(spec)
    return {
        "skill_name": spec.name,
        "doc_slug": doc_slug,
        "input_contract": contract,
    }


def validate_skill_input(
    skill_id: str,
    parsed_input: dict[str, Any],
    manifest_path: str = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Validate a parsed bridge input structurally without running a skill."""
    spec, doc_slug = _resolve_skill_spec(skill_id, manifest_path)
    capabilities = _load_capabilities(manifest_path)
    payload, payload_error = _extract_payload(parsed_input)
    if payload_error is not None:
        result = _base_validation_result(
            valid=False,
            severity="INVALID",
            detected_input_mode="invalid_payload",
            errors=[payload_error],
        )
    elif spec.name == "fund_analysis":
        input_contract = get_skill_input_contract(
            spec.name,
            _input_contract_path_for_manifest(manifest_path),
        )
        result = _validate_fund_analysis(
            parsed_input,
            payload,
            capabilities,
            input_contract,
        )
    elif spec.name in {"news_research", "sentiment_analysis"}:
        result = _validate_mcp_skill(parsed_input, payload, spec)
    elif spec.name == "decision_support":
        result = _validate_decision_support(payload)
    elif spec.name == "thesis_generation":
        result = _validate_thesis_generation(payload)
    else:
        result = _base_validation_result(
            valid=True,
            severity="OK",
            detected_input_mode="generic_payload",
            capability_coverage=_empty_coverage(),
        )
    return {
        "skill_name": spec.name,
        "doc_slug": doc_slug,
        "validation_result": result,
    }


def output_schema_for_skill(
    skill_id: str,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Return a practical bridge output shape summary for a skill."""
    spec, doc_slug = _resolve_skill_spec(skill_id, manifest_path)
    schema = _base_output_schema(spec)
    if spec.name == "fund_analysis":
        artifact_contract = get_skill_artifact_contract(
            spec.name,
            _artifact_contract_path_for_manifest(manifest_path),
        )
        schema["artifacts"] = {
            "contract_version": artifact_contract.get("contract_version"),
            "doc": artifact_contract.get("doc"),
            "known_keys": _artifact_entries_for_output_schema(artifact_contract),
            "artifact_categories": artifact_contract.get("artifact_categories", {}),
            "forbidden_artifacts": list(artifact_contract.get("forbidden_artifacts") or []),
            "notes": [
                "fund_analysis artifact keys are governed by docs/contracts/fund-analysis-artifacts.v1.md and skillpack/artifact-contracts.yaml.",
                "Artifact presence depends on host-supplied portfolio, ledger, NAV, holdings, benchmark, peer, fee, manager, and scenario data.",
                "Optional artifacts are present only when the host supplies the corresponding data; missing optional data may produce PARTIAL status, warnings, report_limitations, or omitted optional artifacts.",
                "Missing data must not be fabricated.",
                "Formal Decision and ExecutionLedger artifacts belong only to decision_support.",
            ],
        }
        schema["evidence_items"] = {
            "produces": ["HardEvidence"],
            "confidence_weight": "HardEvidence confidence_weight is always 1.0.",
        }
        schema["status_values"] = list(artifact_contract.get("status_values") or STATUS_VALUES)
    elif spec.name in {"news_research", "sentiment_analysis"}:
        schema["artifacts"] = {
            "known_keys": [{"key": "mcp_response", "required": False}],
            "notes": [
                "MCP response artifacts echo host-supplied adapter data for testing and auditability.",
            ],
        }
        schema["evidence_items"] = {
            "produces": ["SoftEvidence"],
            "required_fields": [
                "source_type",
                "timestamp",
                "related_entities",
                "claim",
                "confidence_weight",
            ],
        }
    elif spec.name == "decision_support":
        decision_contract = get_decision_contract(
            spec.name,
            Path(manifest_path).parent / "decision-contracts.yaml",
        )
        known_keys: list[dict[str, Any]] = []
        for artifact in decision_contract.get("artifact_keys") or []:
            if isinstance(artifact, dict):
                known_keys.append({
                    "key": str(artifact.get("key", "")),
                    "required": bool(artifact.get("required", False)),
                    "type": str(artifact.get("type", "object")),
                    "produced_when": str(artifact.get("produced_when", "")),
                    "description": str(artifact.get("description", "")),
                })
        schema["artifacts"] = {
            "known_keys": known_keys,
            "formal_outputs": list(decision_contract.get("formal_outputs") or []),
            "notes": [
                "Only decision_support may produce formal Decision and ExecutionLedger outputs.",
                f"Known artifact keys read from skillpack/decision-contracts.yaml.",
                "Active actions require evidence anchors; passive actions may explain insufficient evidence or blockage.",
            ],
        }
        schema["active_actions"] = list(decision_contract.get("active_actions") or [])
        schema["passive_actions"] = list(decision_contract.get("passive_actions") or [])
        schema["decision_fields"] = list(decision_contract.get("decision_fields") or [])
        schema["reason_codes"] = list(decision_contract.get("reason_codes") or [])
        schema["evidence_states"] = list(decision_contract.get("evidence_states") or [])
        schema["input_modes"] = list(decision_contract.get("input_modes") or [])
        schema["status_values"] = list(decision_contract.get("status_values") or STATUS_VALUES)
        schema["evidence_items"] = {
            "produces": [],
            "notes": [
                "decision_support consumes EvidenceGraph; it does not act as an evidence producer.",
            ],
        }
    elif spec.name == "thesis_generation":
        thesis_path = str(Path(manifest_path).parent / "thesis-contracts.yaml")
        contract = get_thesis_contract(spec.name, thesis_path)
        thesis_fields = list(contract.get("thesis_draft_fields") or [])
        formal_forbidden = list(contract.get("formal_outputs_forbidden") or [])
        schema["artifacts"] = {
            "known_keys": [
                {
                    "key": "thesis_draft",
                    "required": True,
                    "fields": thesis_fields,
                },
            ],
            "formal_outputs_forbidden": formal_forbidden,
            "notes": [
                "Produces ThesisDraft only; formal decision generation is forbidden.",
                "ThesisDraft.confidence_assessment has level (LOW/MEDIUM/HIGH), score, and reason.",
                "ThesisDraft.decision_boundary_note is always present and references decision_support.",
            ],
            "forbidden": ["formal_decision_generation"],
            "forbidden_artifacts": ["decision", "decisions", "execution_ledger", "execution_ledgers"],
        }
        schema["evidence_items"] = {
            "produces": [],
            "notes": ["Thesis drafts are artifacts, not formal decisions."],
        }
        schema["thesis_draft_fields"] = thesis_fields
        schema["status_values"] = list(contract.get("status_values") or STATUS_VALUES)
    return {
        "skill_name": spec.name,
        "doc_slug": doc_slug,
        "output_schema": schema,
    }


def _resolve_skill_spec(
    skill_id: str,
    manifest_path: str,
) -> tuple[SkillSpec, str]:
    manifest = load_skillpack_manifest(manifest_path)
    candidate = str(skill_id or "")
    for spec in manifest.skills:
        doc_slug = spec.name.replace("_", "-")
        if candidate in {spec.name, doc_slug}:
            return spec, doc_slug
    raise KeyError(candidate)


def _load_capabilities(manifest_path: str) -> dict[str, Any]:
    cap_path = resolve_resource_path(Path(manifest_path).parent / "capabilities.yaml")
    if not cap_path.exists():
        return {
            "mcp_capabilities": {},
            "host_data_capabilities": {},
            "local_capabilities": {},
        }
    raw = yaml.safe_load(cap_path.read_text(encoding="utf-8")) or {}
    return {
        "mcp_capabilities": dict(raw.get("mcp_capabilities") or {}),
        "host_data_capabilities": dict(raw.get("host_data_capabilities") or {}),
        "local_capabilities": dict(raw.get("local_capabilities") or {}),
    }


def _artifact_contract_path_for_manifest(manifest_path: str) -> Path:
    return Path(manifest_path).parent / "artifact-contracts.yaml"


def _input_contract_path_for_manifest(manifest_path: str) -> Path:
    return Path(manifest_path).parent / "input-contracts.yaml"


def _artifact_entries_for_output_schema(
    artifact_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    fields = (
        "key",
        "required",
        "category",
        "type",
        "produced_when",
        "description",
        "top_level",
        "path",
        "aliases",
        "expected_for_structured_report",
    )
    for artifact in artifact_contract.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        entries.append({
            field: artifact[field]
            for field in fields
            if field in artifact
        })
    return entries


def _accepted_envelope_shapes(skill_name: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "full_skill_input",
            "description": "Full SkillInput-shaped envelope with host-supplied payload.",
            "shape": {
                "task_id": "string",
                "step_id": "string",
                "skill_name": skill_name,
                "payload": "object",
                "kg_context": "object",
                "required_mcp_capabilities": "list[string]",
                "evidence_context": "list[string]",
                "metadata": "object",
                "mcp_responses": "object optional for runtime bridge testing",
            },
        },
        {
            "name": "payload_only",
            "description": "Convenience envelope; bridge fills task_id, step_id, and skill_name.",
            "shape": {
                "payload": "object",
                "mcp_responses": "object optional for runtime bridge testing",
            },
        },
    ]


def _fund_analysis_input_contract(
    capabilities: dict[str, Any],
    input_contract: dict[str, Any],
) -> dict[str, Any]:
    capability_mapping = _capability_field_mapping(input_contract)
    return {
        "contract_version": input_contract.get("contract_version"),
        "doc": input_contract.get("doc"),
        "accepted_envelope_shapes": list(input_contract.get("accepted_envelope_shapes") or []),
        "minimum_required": list(input_contract.get("minimum_required") or []),
        "recommended": _recommended_field_keys(input_contract),
        "optional": _optional_field_keys(input_contract),
        "required_mcp_capabilities": list(input_contract.get("required_mcp_capabilities") or []),
        "host_owned_data_capabilities": _host_data_capabilities_for_skill(
            "fund_analysis",
            capabilities,
            capability_mapping,
        ),
        "host_data_capability_fields": capability_mapping,
        "validation": dict(input_contract.get("validation") or {}),
        "degradation_policy": list(input_contract.get("degradation_policy") or []),
    }


def _mcp_skill_input_contract(
    spec: SkillSpec,
    capabilities: dict[str, Any],
) -> dict[str, Any]:
    return {
        "accepted_envelope_shapes": _accepted_envelope_shapes(spec.name),
        "minimum_required": [
            {
                "mode": "host_payload_plus_mcp",
                "description": "Host supplies a broad payload and MCP data through its own provider layer.",
                "required": ["payload object"],
                "runtime_bridge_testing": [
                    f"mcp_responses.{name}"
                    for name in spec.requires_mcp
                ],
            }
        ],
        "recommended": [
            "query",
            "related_entities",
            "time_window",
            "source_quality_preferences",
        ],
        "optional": [
            "locale",
            "market",
            "filters",
            "max_items",
            "dedupe_keys",
        ],
        "required_mcp_capabilities": list(spec.requires_mcp or []),
        "host_owned_data_capabilities": _mcp_capabilities_for_skill(
            spec.name,
            capabilities,
        ),
        "degradation_policy": [
            "mcp_responses may be supplied for runtime bridge testing; real provider calls belong to the external host.",
            "The bridge validates MCP response presence only; it does not call providers or the network.",
            "The skill Markdown keeps payload fields broad unless a stricter host contract is supplied.",
        ],
    }


def _decision_support_input_contract(spec: SkillSpec) -> dict[str, Any]:
    return {
        "accepted_envelope_shapes": _accepted_envelope_shapes(spec.name),
        "minimum_required": [
            {
                "mode": "evidence_graph_decision_support",
                "required": ["payload.evidence_graph"],
                "description": "Consumes a host-compiled EvidenceGraph and emits Decision / ExecutionLedger artifacts.",
            }
        ],
        "recommended": [
            "objective",
            "portfolio_context",
            "risk_profile",
            "constraints",
            "requested_action or trade_plan",
        ],
        "optional": [
            "target_trade_amount",
            "time_horizon",
            "critique",
            "selected_trade_ids",
        ],
        "required_mcp_capabilities": [],
        "host_owned_data_capabilities": [],
        "degradation_policy": [
            "Active actions (BUY, SELL, INCREASE, REDUCE) must be anchored to evidence.",
            "Passive actions may be anchorless only when insufficient evidence or blockage is explained.",
            "--explain-input and --validate-input never create decisions.",
        ],
    }


def _thesis_generation_input_contract(spec: SkillSpec) -> dict[str, Any]:
    return {
        "accepted_envelope_shapes": _accepted_envelope_shapes(spec.name),
        "minimum_required": [
            {
                "mode": "thesis_draft",
                "required": ["payload object"],
                "description": "Produces a ThesisDraft artifact from host context.",
            }
        ],
        "recommended": [
            "thesis_question or topic",
            "evidence_items or evidence_graph",
            "evidence_context",
            "fund_analysis_report",
            "related_entities",
        ],
        "optional": [
            "artifacts",
            "research_focus",
            "constraints",
            "risk_profile",
            "audience",
            "draft_options",
        ],
        "required_mcp_capabilities": [],
        "host_owned_data_capabilities": [],
        "degradation_policy": [
            "Thesis generation produces ThesisDraft only.",
            "Formal decision generation is forbidden and belongs to decision_support.",
            "If evidence is missing, produces a valid draft with LOW confidence and missing_evidence / limitations.",
        ],
    }


def _generic_input_contract(spec: SkillSpec) -> dict[str, Any]:
    return {
        "accepted_envelope_shapes": _accepted_envelope_shapes(spec.name),
        "minimum_required": [{"mode": "generic_payload", "required": ["payload object"]}],
        "recommended": [],
        "optional": [],
        "required_mcp_capabilities": list(spec.requires_mcp or []),
        "host_owned_data_capabilities": [],
        "degradation_policy": [
            "This structural contract is host-assistive and does not run the skill.",
        ],
    }


def _host_data_capabilities_for_skill(
    skill_name: str,
    capabilities: dict[str, Any],
    capability_field_mapping: dict[str, list[str]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name, info in sorted((capabilities.get("host_data_capabilities") or {}).items()):
        if skill_name not in list(info.get("required_by") or []):
            continue
        result.append({
            "name": name,
            "owner": "host",
            "payload_fields": capability_field_mapping.get(name, []),
            "description": str(info.get("description", "")).strip(),
            "required": bool(info.get("required", False)),
            "missing_behavior": info.get("missing_behavior"),
        })
    return result


def _mcp_capabilities_for_skill(
    skill_name: str,
    capabilities: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name, info in sorted((capabilities.get("mcp_capabilities") or {}).items()):
        if skill_name not in list(info.get("required_by") or []):
            continue
        result.append({
            "name": name,
            "owner": "host",
            "category": "mcp_capability",
            "description": str(info.get("description", "")).strip(),
        })
    return result


def _extract_payload(
    parsed_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(parsed_input, dict):
        return {}, _error(
            "INVALID_ENVELOPE",
            "input must be a JSON object",
            "input",
        )
    payload = parsed_input.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return {}, _error(
            "INVALID_PAYLOAD",
            f"input.payload must be a JSON object, got {type(payload).__name__}",
            "payload",
        )
    return payload, None


def _validate_fund_analysis(
    parsed_input: dict[str, Any],
    payload: dict[str, Any],
    capabilities: dict[str, Any],
    input_contract: dict[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    detected_mode = ""

    portfolio = payload.get("portfolio")
    portfolio_obj = portfolio if isinstance(portfolio, dict) else {}
    positions = portfolio_obj.get("positions")
    positions_list = positions if isinstance(positions, list) else []
    has_positions_field = isinstance(positions, list)
    usable_positions = [
        position
        for position in positions_list
        if isinstance(position, dict) and _non_empty(position.get("fund_code"))
    ]

    has_portfolio_mode = bool(usable_positions)
    if has_positions_field and not usable_positions:
        errors.append(_error(
            "NO_USABLE_FUND_CODE",
            "payload.portfolio.positions exists but contains no usable fund_code",
            "payload.portfolio.positions",
        ))
    if has_portfolio_mode:
        detected_mode = "portfolio_snapshot"
        missing_current_value = [
            str(position.get("fund_code"))
            for position in usable_positions
            if not _non_empty(position.get("current_value"))
        ]
        if missing_current_value:
            warnings.append(_warning(
                "MISSING_CURRENT_VALUE",
                "portfolio positions without current_value limit useful portfolio analysis",
                "payload.portfolio.positions[].current_value",
                {"fund_codes": missing_current_value},
            ))

    transactions = payload.get("transactions")
    current_nav = payload.get("current_nav")
    has_transactions = isinstance(transactions, list) and bool(transactions)
    has_current_nav = isinstance(current_nav, dict) and bool(current_nav)
    has_as_of_date = _non_empty(payload.get("as_of_date")) or _non_empty(
        portfolio_obj.get("as_of_date")
    )
    has_ledger_mode = has_transactions and has_current_nav and has_as_of_date
    if has_ledger_mode and not detected_mode:
        detected_mode = "ledger_derived"
    if has_transactions and has_current_nav and not has_as_of_date:
        errors.append(_error(
            "MISSING_AS_OF_DATE",
            "transactions + current_nav mode requires payload.as_of_date or payload.portfolio.as_of_date",
            "payload.as_of_date",
        ))

    has_related_entities = _has_related_entities(parsed_input, payload)
    if not detected_mode and has_related_entities and not errors:
        detected_mode = "related_entities_baseline"
        warnings.append(_warning(
            "BASELINE_ONLY",
            "related_entities is a baseline-only compatibility path; structured portfolio analysis is not possible",
            "payload.related_entities",
        ))

    if not detected_mode and not errors:
        errors.append(_error(
            "MISSING_MINIMUM_INPUT",
            "fund_analysis requires portfolio.positions with fund_code, transactions + current_nav + as_of_date, or related_entities baseline",
            "payload",
        ))

    recommended_fields = _recommended_field_keys(input_contract)
    optional_fields = _optional_field_keys(input_contract)
    missing_recommended = [
        field for field in recommended_fields if not _has_payload_field(payload, field)
    ]
    missing_optional = [
        field for field in optional_fields if not _has_payload_field(payload, field)
    ]
    for field in missing_recommended:
        warnings.append(_warning(
            "MISSING_RECOMMENDED",
            f"missing recommended field: {field}",
            f"payload.{field}",
        ))

    coverage = _fund_capability_coverage(
        payload,
        capabilities,
        _capability_field_mapping(input_contract),
    )
    if errors:
        valid = False
        severity = "INVALID"
        detected_mode = detected_mode or "invalid"
    elif detected_mode == "related_entities_baseline":
        valid = True
        severity = "PARTIAL"
    elif any(w["code"] == "MISSING_CURRENT_VALUE" for w in warnings):
        valid = True
        severity = "PARTIAL"
    else:
        valid = True
        severity = "OK"

    return _base_validation_result(
        valid=valid,
        severity=severity,
        errors=errors,
        warnings=warnings,
        missing_recommended=missing_recommended,
        missing_optional=missing_optional,
        detected_input_mode=detected_mode,
        capability_coverage=coverage,
    )


def _validate_mcp_skill(
    parsed_input: dict[str, Any],
    payload: dict[str, Any],
    spec: SkillSpec,
) -> dict[str, Any]:
    mcp_responses = parsed_input.get("mcp_responses")
    response_keys = set(mcp_responses.keys()) if isinstance(mcp_responses, dict) else set()
    required = list(spec.requires_mcp or [])
    missing = [name for name in required if name not in response_keys]
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if missing:
        errors.append(_error(
            "MISSING_MCP_CAPABILITY",
            "runtime bridge testing requires mcp_responses for manifest-required MCP capabilities",
            "mcp_responses",
            {"missing_mcp_capabilities": missing},
        ))
        warnings.append(_warning(
            "HOST_OWNS_MCP",
            "real MCP provider calls belong to the external host; validation does not call providers",
            "mcp_responses",
        ))

    coverage = _coverage(
        expected=required,
        present=[name for name in required if name in response_keys],
    )
    result = _base_validation_result(
        valid=not missing,
        severity="INVALID" if missing else "OK",
        errors=errors,
        warnings=warnings,
        detected_input_mode="mcp_responses" if response_keys else "missing_mcp_responses",
        capability_coverage=coverage,
    )
    result["required_mcp_capabilities"] = required
    result["missing_mcp_capabilities"] = missing
    result["payload_fields_present"] = sorted(payload.keys())
    return result


def _validate_decision_support(payload: dict[str, Any]) -> dict[str, Any]:
    graph = payload.get("evidence_graph")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not _evidence_graph_non_empty(graph):
        errors.append(_error(
            "MISSING_EVIDENCE_GRAPH",
            "decision_support requires payload.evidence_graph with at least one evidence item",
            "payload.evidence_graph",
        ))
    requested_action = str(payload.get("requested_action") or "").upper()
    if requested_action in ACTIVE_ACTIONS and not _evidence_graph_non_empty(graph):
        warnings.append(_warning(
            "ACTIVE_ACTION_REQUIRES_EVIDENCE",
            "active requested actions must be anchored to evidence",
            "payload.requested_action",
        ))
    return _base_validation_result(
        valid=not errors,
        severity="INVALID" if errors else "OK",
        errors=errors,
        warnings=warnings,
        missing_recommended=[
            field
            for field in ["objective", "portfolio_context", "constraints"]
            if not _has_payload_field(payload, field)
        ],
        missing_optional=[
            field
            for field in ["target_trade_amount", "time_horizon", "critique"]
            if not _has_payload_field(payload, field)
        ],
        detected_input_mode="evidence_graph" if not errors else "missing_evidence_graph",
        capability_coverage=_empty_coverage(),
    )


def _validate_thesis_generation(payload: dict[str, Any]) -> dict[str, Any]:
    return _base_validation_result(
        valid=True,
        severity="OK",
        warnings=[
            _warning(
                "NO_FORMAL_DECISION",
                "thesis_generation produces ThesisDraft only; formal decision generation is forbidden",
                "payload",
            )
        ],
        missing_recommended=[
            field
            for field in ["objective", "evidence_context", "research_context"]
            if not _has_payload_field(payload, field)
        ],
        missing_optional=[
            field
            for field in ["constraints", "audience", "draft_options"]
            if not _has_payload_field(payload, field)
        ],
        detected_input_mode="thesis_draft",
        capability_coverage=_empty_coverage(),
    )


def _base_output_schema(spec: SkillSpec) -> dict[str, Any]:
    return {
        "bridge_envelope": {
            "ok": "boolean; true when the bridge command succeeds",
            "skill_name": spec.name,
            "step_id": "string for normal skill execution",
            "status": "SkillOutput.status for normal execution",
            "artifacts": "object",
            "evidence_items": "list",
            "warnings": "list",
            "errors": "list",
            "used_mcp_capabilities": "list[string]",
            "metadata": "object with manifest_path and runtime/MCP metadata",
        },
        "skill_output_fields": {
            "step_id": "string",
            "skill_name": "runtime skill id",
            "evidence_items": "list of evidence item dicts",
            "artifacts": "JSON object of skill-specific outputs",
            "warnings": "list[string]",
            "errors": "list of SkillError-shaped dicts (code, message, details, recoverable)",
            "used_mcp_capabilities": "list[string]",
            "status": "OK | PARTIAL | FAILED",
        },
        "artifacts": {
            "known_keys": [],
            "notes": ["Artifact keys vary by skill and available host-owned data."],
        },
        "evidence_items": {
            "produces": list(spec.produces or []),
        },
        "status_values": list(STATUS_VALUES),
    }


def _base_validation_result(
    *,
    valid: bool,
    severity: str,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    missing_recommended: list[str] | None = None,
    missing_optional: list[str] | None = None,
    detected_input_mode: str,
    capability_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "valid": bool(valid),
        "severity": severity,
        "errors": list(errors or []),
        "warnings": list(warnings or []),
        "missing_recommended": list(missing_recommended or []),
        "missing_optional": list(missing_optional or []),
        "detected_input_mode": detected_input_mode,
        "capability_coverage": capability_coverage or _empty_coverage(),
    }


def _fund_capability_coverage(
    payload: dict[str, Any],
    capabilities: dict[str, Any],
    capability_field_mapping: dict[str, list[str]],
) -> dict[str, Any]:
    expected = [
        name
        for name, info in sorted((capabilities.get("host_data_capabilities") or {}).items())
        if "fund_analysis" in list(info.get("required_by") or [])
    ]
    present = [
        name
        for name in expected
        if any(_has_payload_field(payload, field) for field in capability_field_mapping.get(name, []))
    ]
    return _coverage(expected=expected, present=present)


def _recommended_field_keys(input_contract: dict[str, Any]) -> list[str]:
    return _field_keys(input_contract.get("recommended_fields") or [])


def _optional_field_keys(input_contract: dict[str, Any]) -> list[str]:
    return _field_keys(input_contract.get("optional_fields") or [])


def _field_keys(fields: list[Any]) -> list[str]:
    keys: list[str] = []
    for field in fields:
        if isinstance(field, dict) and field.get("key") is not None:
            keys.append(str(field["key"]))
        elif isinstance(field, str):
            keys.append(field)
    return keys


def _capability_field_mapping(input_contract: dict[str, Any]) -> dict[str, list[str]]:
    raw_mapping = input_contract.get("host_data_capability_fields") or {}
    if not isinstance(raw_mapping, dict):
        return {}
    result: dict[str, list[str]] = {}
    for name, info in raw_mapping.items():
        if isinstance(info, dict):
            fields = info.get("payload_fields") or []
        else:
            fields = info
        result[str(name)] = [str(field) for field in fields] if isinstance(fields, list) else []
    return result


def _coverage(expected: list[str], present: list[str]) -> dict[str, Any]:
    present_set = set(present)
    missing = [name for name in expected if name not in present_set]
    score = round(len(present_set) / len(expected), 3) if expected else 0.0
    return {
        "score": score,
        "present": [name for name in expected if name in present_set],
        "missing": missing,
    }


def _empty_coverage() -> dict[str, Any]:
    return {"score": 0.0, "present": [], "missing": []}


def _has_payload_field(payload: dict[str, Any], field: str) -> bool:
    if "." not in field:
        return _truthy(payload.get(field))
    current: Any = payload
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return _truthy(current)


def _truthy(value: Any) -> bool:
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return value not in (None, "")


def _non_empty(value: Any) -> bool:
    return value not in (None, "")


def _has_related_entities(
    parsed_input: dict[str, Any],
    payload: dict[str, Any],
) -> bool:
    related_entities = payload.get("related_entities")
    if isinstance(related_entities, list) and bool(related_entities):
        return True
    kg_context = parsed_input.get("kg_context")
    if isinstance(kg_context, dict):
        fund_codes = kg_context.get("fund_codes")
        if isinstance(fund_codes, list) and bool(fund_codes):
            return True
    return False


def _evidence_graph_non_empty(graph: Any) -> bool:
    if not isinstance(graph, dict):
        return False
    items = graph.get("items")
    if isinstance(items, dict):
        return bool(items)
    if isinstance(items, list):
        return bool(items)
    evidence_items = graph.get("evidence_items")
    if isinstance(evidence_items, list):
        return bool(evidence_items)
    return False


def _error(
    code: str,
    message: str,
    path: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "path": path,
        "details": dict(details or {}),
    }


def _warning(
    code: str,
    message: str,
    path: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "path": path,
        "details": dict(details or {}),
    }
