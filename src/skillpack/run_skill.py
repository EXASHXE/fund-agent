"""Runtime bridge — a thin local JSON-in / JSON-out CLI over existing
fund-agent manifest runtime skills.

Architecture constraints (do not relax):

- The bridge is a thin shim over the existing manifest runtime
  skills. It does not import provider SDKs, does not call the
  network, does not run an agent loop, and does not become a daemon
  or server.
- The bridge resolves runtime classes from the manifest
  ``skillpack/fund-agent.skillpack.yaml`` via
  ``src.skillpack.loader``. It does not hardcode runtime classes.
- For skills that require MCP, the bridge accepts an in-memory
  ``mcp_responses`` block in the input JSON. The bridge does not
  spawn subprocesses for handlers; the host owns the actual
  provider calls. If no MCP response is provided for a required
  capability, the bridge returns a clear PARTIAL/FAILED skill
  output explaining the host-owned MCP requirement.
- Stdout is JSON only. Diagnostics go to stderr. Exit code 0
  means the bridge itself succeeded; the embedded skill status
  is reported in the JSON envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput, SkillOutput
from src.tools.adapters.mcp import (
    InMemoryMCPHostAdapter,
    MCPCapability,
    MCPHostAdapter,
)

DEFAULT_MANIFEST_PATH = "skillpack/fund-agent.skillpack.yaml"

# Bridge-level error codes (distinct from SkillError.code values).
BRIDGE_ERROR_CODES = frozenset({
    "INVALID_INPUT",
    "UNKNOWN_SKILL",
    "RUNTIME_LOAD_FAILED",
    "SKILL_RUN_FAILED",
    "JSON_SERIALIZATION_FAILED",
    "MISSING_MCP_CAPABILITY",
})

# Slug -> runtime_id map for the optional convenience that accepts
# hyphenated agent-facing skill names on the CLI. The mapping is
# derived from the manifest; this is a static fallback only used
# when the manifest is unavailable.
SLUG_TO_RUNTIME_ID = {
    "fund-analysis": "fund_analysis",
    "decision-support": "decision_support",
    "news-research": "news_research",
    "sentiment-analysis": "sentiment_analysis",
    "thesis-generation": "thesis_generation",
}


def _emit_envelope(
    envelope: dict[str, Any],
    *,
    pretty: bool,
    output_path: Path | None,
) -> int:
    """Serialize ``envelope`` to JSON and write it to ``output_path``
    or stdout. Returns the intended process exit code.

    The caller is responsible for ``sys.exit(returncode)`` if running
    as ``__main__``.

    Exit-code semantics:

    - ``0`` — the bridge itself succeeded; the original envelope
      had ``ok=true`` and was serialized successfully.
    - ``2`` — bridge-level failure. This includes any case where a
      JSON serialization fallback is used, even if the original
      envelope had ``ok=true`` (a non-serializable output is a
      bridge-level failure regardless of skill intent).
    """
    indent = 2 if pretty else None
    separators = None if pretty else (",", ":")
    fallback_used = False
    try:
        text = json.dumps(envelope, indent=indent, separators=separators, default=str)
    except (TypeError, ValueError) as exc:
        fallback_used = True
        fallback = {
            "ok": False,
            "error": {
                "code": "JSON_SERIALIZATION_FAILED",
                "message": f"bridge output is not JSON-serializable: {exc}",
                "details": {"exception_type": type(exc).__name__},
            },
        }
        text = json.dumps(fallback)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    if fallback_used:
        return 2
    return 0 if envelope.get("ok") is True else 2


def _read_input(
    input_arg: str | None,
    *,
    skill_name: str,
    input_text: str | None = None,
) -> dict[str, Any]:
    """Read and parse the bridge input.

    ``input_arg`` is a CLI path argument (or ``-`` for stdin). When
    ``input_text`` is provided (already read from stdin), it overrides
    ``input_arg`` and is used directly.

    Returns the parsed dict, or raises ``ValueError`` with a
    human-readable message.
    """
    if input_text is not None:
        raw = input_text
    elif input_arg == "-":
        raw = sys.stdin.read()
    elif input_arg is not None:
        path = Path(input_arg)
        if not path.exists():
            raise ValueError(f"input file not found: {input_arg}")
        raw = path.read_text(encoding="utf-8")
    else:
        raise ValueError("no input provided (use --input <path> or --input -)")
    text = raw.strip()
    if not text:
        raise ValueError("input is empty; expected a JSON object")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"input is not valid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno})"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"input must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def _build_skill_input(
    parsed: dict[str, Any],
    *,
    skill_name: str,
) -> SkillInput:
    """Build a :class:`SkillInput` from a parsed input dict.

    Accepts either a full ``SkillInput``-shaped envelope or a
    convenience ``{"payload": {...}}`` envelope.
    """
    if "payload" in parsed and "skill_name" not in parsed:
        payload = parsed.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError(
                f"input.payload must be a JSON object, got {type(payload).__name__}"
            )
        return SkillInput(
            task_id=str(parsed.get("task_id") or "runtime-bridge-task"),
            step_id=str(parsed.get("step_id") or f"{skill_name}-1"),
            skill_name=skill_name,
            payload=payload,
            kg_context=dict(parsed.get("kg_context") or {}),
            required_mcp_capabilities=list(
                parsed.get("required_mcp_capabilities") or []
            ),
            evidence_context=list(parsed.get("evidence_context") or []),
            metadata=dict(parsed.get("metadata") or {}),
        )
    # Full envelope: trust the fields as-is, but coerce defaults
    # to keep the bridge robust against partial envelopes.
    payload = parsed.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError(
            f"input.payload must be a JSON object, got {type(payload).__name__}"
        )
    return SkillInput(
        task_id=str(parsed.get("task_id") or "runtime-bridge-task"),
        step_id=str(parsed.get("step_id") or f"{skill_name}-1"),
        skill_name=skill_name,
        payload=payload,
        kg_context=dict(parsed.get("kg_context") or {}),
        required_mcp_capabilities=list(
            parsed.get("required_mcp_capabilities") or []
        ),
        evidence_context=list(parsed.get("evidence_context") or []),
        metadata=dict(parsed.get("metadata") or {}),
    )


def _build_mcp_adapter(
    mcp_responses: dict[str, Any] | None,
    required_capabilities: list[str],
) -> tuple[MCPHostAdapter | None, list[str]]:
    """Build an in-memory MCP adapter from the bridge input's
    ``mcp_responses`` block. Returns ``(adapter, missing)`` where
    ``missing`` is the list of capability names that were required
    by the skill but absent from the input.

    If ``mcp_responses`` is None, returns ``(None, required_capabilities)``
    so the caller can report a clear PARTIAL/FAILED envelope.
    """
    if not required_capabilities:
        return None, []
    if not mcp_responses:
        return None, list(required_capabilities)
    capabilities: list[MCPCapability] = []
    handlers: dict[str, Any] = {}
    for name in required_capabilities:
        response = mcp_responses.get(name)
        if response is None:
            continue
        capabilities.append(
            MCPCapability(
                name=name,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        )
        # Wrap the canned response so MCP-capable skills receive
        # a normal-looking {"ok": true, "data": ...} payload.
        canned = response
        def _handler(payload: dict, _canned: Any = canned) -> dict:
            return {"ok": True, "data": _canned}
        handlers[name] = _handler
    if not capabilities:
        return None, list(required_capabilities)
    adapter = InMemoryMCPHostAdapter(capabilities=capabilities, handlers=handlers)
    missing = [n for n in required_capabilities if n not in handlers]
    return adapter, missing


def _envelope_from_output(
    output: SkillOutput,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap a :class:`SkillOutput` in the bridge envelope."""
    payload = {
        "ok": True,
        "skill_name": output.skill_name,
        "step_id": output.step_id,
        "status": output.status,
        "artifacts": dict(output.artifacts or {}),
        "evidence_items": [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in output.evidence_items
        ],
        "warnings": list(output.warnings or []),
        "errors": [
            err.to_dict() if hasattr(err, "to_dict") else err
            for err in output.errors
        ],
        "used_mcp_capabilities": list(output.used_mcp_capabilities or []),
        "metadata": dict(metadata or {}),
    }
    return payload


def _list_skills_envelope(
    manifest_path: str,
) -> dict[str, Any]:
    """Build the ``--list-skills`` envelope from the manifest."""
    manifest = load_skillpack_manifest(manifest_path)
    # Build a reverse map (runtime_id -> doc_slug) for the
    # convenience of callers that want both identifiers.
    runtime_to_slug = {rid: slug for slug, rid in SLUG_TO_RUNTIME_ID.items()}
    skills = []
    for spec in manifest.skills:
        skills.append({
            "runtime_id": spec.name,
            "doc_slug": runtime_to_slug.get(spec.name, ""),
            "runtime": spec.runtime,
            "requires_mcp": list(spec.requires_mcp or []),
            "produces": list(spec.produces or []),
            "forbidden": list(spec.forbidden or []),
        })
    return {
        "ok": True,
        "manifest_version": manifest.version,
        "schema_version": manifest.schema_version,
        "skills": skills,
        "metadata": {"command": "list-skills", "manifest_path": manifest_path},
    }


def _resolve_skill(
    skill_arg: str,
    manifest_path: str,
) -> tuple[str, str, list[str]]:
    """Resolve a CLI ``--skill`` value to
    ``(runtime_id, runtime_path, manifest_requires_mcp)``.

    Accepts both runtime IDs (``fund_analysis``) and agent-facing
    hyphenated slugs (``fund-analysis``). The slug form is a
    convenience only and is documented as such.

    The returned ``manifest_requires_mcp`` is the canonical list
    declared by ``skillpack/fund-agent.skillpack.yaml`` for this
    runtime skill. The bridge unions this with the host's
    ``SkillInput.required_mcp_capabilities`` to compute the
    effective required MCP set.
    """
    manifest = load_skillpack_manifest(manifest_path)
    candidate = skill_arg
    if "-" in candidate and "_" not in candidate:
        candidate = SLUG_TO_RUNTIME_ID.get(candidate, candidate)
    for spec in manifest.skills:
        if spec.name == candidate:
            return spec.name, spec.runtime, list(spec.requires_mcp or [])
    raise KeyError(candidate)


def _effective_required_mcp(
    manifest_requires: list[str],
    skill_input_requires: list[str],
) -> list[str]:
    """Compute the effective required MCP capability set as the
    union of the manifest declaration and the host-supplied
    ``SkillInput.required_mcp_capabilities``.

    Order is preserved (manifest first, then any extras the host
    added that are not already declared), with duplicates removed.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for name in list(manifest_requires or []) + list(skill_input_requires or []):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def run_bridge(
    *,
    skill_name: str | None,
    input_path: str | None,
    input_text: str | None = None,
    output_path: Path | None = None,
    pretty: bool = False,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    list_skills: bool = False,
) -> int:
    """Top-level bridge entry point.

    Returns the intended process exit code. Writes JSON to
    ``output_path`` (or stdout when ``output_path`` is None) and
    diagnostics to stderr.
    """
    if list_skills:
        try:
            envelope = _list_skills_envelope(manifest_path)
        except Exception as exc:  # manifest load failure, etc.
            return _emit_envelope(
                {
                    "ok": False,
                    "error": {
                        "code": "RUNTIME_LOAD_FAILED",
                        "message": f"failed to load manifest: {exc}",
                        "details": {"exception_type": type(exc).__name__},
                    },
                },
                pretty=pretty,
                output_path=output_path,
            )
        return _emit_envelope(envelope, pretty=pretty, output_path=output_path)

    if not skill_name:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "--skill is required unless --list-skills is passed",
                    "details": {},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    try:
        runtime_id, runtime_path, manifest_requires_mcp = _resolve_skill(
            skill_name, manifest_path
        )
    except KeyError:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "UNKNOWN_SKILL",
                    "message": f"unknown skill: {skill_name!r}",
                    "details": {
                        "valid_runtime_ids": sorted(SLUG_TO_RUNTIME_ID.values()),
                    },
                },
            },
            pretty=pretty,
            output_path=output_path,
        )
    except Exception as exc:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "RUNTIME_LOAD_FAILED",
                    "message": f"failed to resolve skill: {exc}",
                    "details": {"exception_type": type(exc).__name__},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    try:
        parsed = _read_input(input_path, skill_name=runtime_id, input_text=input_text)
    except ValueError as exc:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": str(exc),
                    "details": {},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    try:
        skill_input = _build_skill_input(parsed, skill_name=runtime_id)
    except ValueError as exc:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": str(exc),
                    "details": {},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    mcp_responses = parsed.get("mcp_responses") if isinstance(parsed, dict) else None
    effective_required_mcp = _effective_required_mcp(
        manifest_requires_mcp,
        list(skill_input.required_mcp_capabilities or []),
    )
    adapter, missing_mcp = _build_mcp_adapter(
        mcp_responses, effective_required_mcp
    )

    try:
        skill_cls = resolve_runtime(runtime_path)
    except Exception as exc:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "RUNTIME_LOAD_FAILED",
                    "message": f"failed to import runtime class: {exc}",
                    "details": {
                        "runtime": runtime_path,
                        "exception_type": type(exc).__name__,
                    },
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    try:
        skill_instance = skill_cls(mcp_adapter=adapter) if adapter is not None else skill_cls()
    except TypeError:
        # Skill constructors vary; some accept mcp_adapter, some
        # don't. Fall back to a no-arg constructor and let the
        # skill manage MCP via its own state if needed.
        try:
            skill_instance = skill_cls()
        except Exception as exc:
            return _emit_envelope(
                {
                    "ok": False,
                    "error": {
                        "code": "RUNTIME_LOAD_FAILED",
                        "message": f"failed to instantiate skill: {exc}",
                        "details": {"exception_type": type(exc).__name__},
                    },
                },
                pretty=pretty,
                output_path=output_path,
            )
    except Exception as exc:
        return _emit_envelope(
            {
                "ok": False,
                "error": {
                    "code": "RUNTIME_LOAD_FAILED",
                    "message": f"failed to instantiate skill: {exc}",
                    "details": {"exception_type": type(exc).__name__},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    try:
        output = skill_instance.run(skill_input)
    except Exception as exc:
        return _emit_envelope(
            {
                "ok": False,
                "skill_name": runtime_id,
                "error": {
                    "code": "SKILL_RUN_FAILED",
                    "message": f"skill raised: {exc}",
                    "details": {"exception_type": type(exc).__name__},
                },
            },
            pretty=pretty,
            output_path=output_path,
        )

    metadata = {
        "manifest_path": manifest_path,
        "runtime_path": runtime_path,
        "required_mcp_capabilities": list(effective_required_mcp),
        "missing_mcp_capabilities": list(missing_mcp),
    }
    envelope = _envelope_from_output(output, metadata=metadata)
    # If the skill required MCP and the bridge could not provide
    # at least one required capability, downgrade ok to False so
    # callers can branch on it. The embedded skill status / errors
    # remain in the envelope for transparency.
    if missing_mcp:
        envelope["ok"] = False
        envelope["error"] = {
            "code": "MISSING_MCP_CAPABILITY",
            "message": (
                "skill requires MCP capabilities that the bridge could not provide; "
                "host-owned MCP adapter is required"
            ),
            "details": {"missing_mcp_capabilities": list(missing_mcp)},
        }
    return _emit_envelope(envelope, pretty=pretty, output_path=output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_skill.py",
        description=(
            "fund-agent runtime bridge: a thin local JSON-in / JSON-out CLI "
            "over existing manifest runtime skills. It does not fetch data, "
            "does not import provider SDKs, and does not run an agent loop. "
            "The host owns MCP providers, network access, and orchestration."
        ),
    )
    parser.add_argument(
        "--skill",
        default=None,
        help=(
            "Runtime ID (fund_analysis, decision_support, news_research, "
            "sentiment_analysis, thesis_generation) or hyphenated agent-facing "
            "slug (fund-analysis, decision-support, ...)."
        ),
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "Path to a JSON input file. Use '-' to read JSON from stdin. "
            "The input is either a full SkillInput envelope or a convenience "
            "{'payload': {...}} shape."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST_PATH,
        help=(
            "Path to the skillpack manifest YAML. "
            f"Defaults to {DEFAULT_MANIFEST_PATH}."
        ),
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List the manifest runtime skills and exit. JSON envelope on stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output (indent=2).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = Path(args.output) if args.output else None
    return run_bridge(
        skill_name=args.skill,
        input_path=args.input,
        output_path=output_path,
        pretty=args.pretty,
        manifest_path=args.manifest,
        list_skills=args.list_skills,
    )


if __name__ == "__main__":
    raise SystemExit(main())
