"""Tests for the runtime bridge's MCP required-capability resolution.

The bridge must resolve required MCP capabilities from two sources:

1. The manifest ``skillpack/fund-agent.skillpack.yaml`` declares
   ``requires_mcp`` for each runtime skill (e.g. ``news_research``
   requires ``web_search`` and ``financial_news``).
2. The host's ``SkillInput.required_mcp_capabilities`` may add
   additional requirements.

The effective required set is the union of (1) and (2). The bridge
must build its ``InMemoryMCPHostAdapter`` over the effective set,
report missing capabilities honestly, and never silently drop a
manifest-required capability just because the host did not echo it
in the input.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def _run_cli(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=60,
    )


def _write_input(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "in.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_news_research_without_mcp_responses_reports_missing_capabilities(
    tmp_path: Path,
) -> None:
    """``news_research`` requires ``web_search`` and ``financial_news``
    per the manifest. Without ``mcp_responses`` the bridge must
    surface both capabilities in ``metadata.missing_mcp_capabilities``
    and downgrade ``ok`` to False with ``error.code =
    MISSING_MCP_CAPABILITY``.
    """
    payload = {
        "payload": {"query": "fund:110011"},
    }
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "news_research",
        "--input", str(input_path),
    ])
    assert proc.returncode == 2, (
        f"bridge should fail (rc=2) when required MCP is missing; "
        f"got rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["error"]["code"] == "MISSING_MCP_CAPABILITY"
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "web_search" in missing
    assert "financial_news" in missing
    # Both manifest requirements must be present in the metadata
    # declared required_mcp_capabilities.
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "web_search" in required
    assert "financial_news" in required


def test_sentiment_analysis_without_mcp_responses_reports_missing_capability(
    tmp_path: Path,
) -> None:
    """``sentiment_analysis`` requires ``social_sentiment`` per the
    manifest. Without ``mcp_responses`` the bridge must surface that
    capability in the missing list.
    """
    payload = {
        "payload": {"query": "fund:110011", "related_entities": ["110011"]},
    }
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "sentiment_analysis",
        "--input", str(input_path),
    ])
    assert proc.returncode == 2, (
        f"bridge should fail (rc=2) when required MCP is missing; "
        f"got rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["error"]["code"] == "MISSING_MCP_CAPABILITY"
    missing = out["metadata"]["missing_mcp_capabilities"]
    assert "social_sentiment" in missing
    assert "social_sentiment" in out["metadata"]["required_mcp_capabilities"]


def test_news_research_with_canned_mcp_responses_runs(tmp_path: Path) -> None:
    """When the host supplies ``mcp_responses`` for all manifest-
    required capabilities, the bridge builds an
    ``InMemoryMCPHostAdapter`` and the skill runs to OK.
    """
    payload = {
        "payload": {"query": "fund:110011"},
        "mcp_responses": {
            "web_search": {
                "items": [
                    {
                        "source_type": "news",
                        "timestamp": "2026-05-01T00:00:00",
                        "related_entities": ["110011"],
                        "claim": "Test news item",
                        "direction": "neutral",
                        "confidence_weight": 0.5,
                    }
                ]
            },
            "financial_news": {
                "items": [
                    {
                        "source_type": "financial_news",
                        "timestamp": "2026-05-02T00:00:00",
                        "related_entities": ["110011"],
                        "claim": "Earnings beat expectations",
                        "direction": "positive",
                        "confidence_weight": 0.7,
                    }
                ]
            },
        },
    }
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "news_research",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0, (
        f"bridge should succeed with canned MCP; got rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    # No missing MCP once all manifest requirements are supplied.
    assert out["metadata"]["missing_mcp_capabilities"] == []
    assert out["status"] in ("OK", "PARTIAL")
    assert out["skill_name"] == "news_research"


def test_convenience_input_respects_manifest_requires_mcp(tmp_path: Path) -> None:
    """A convenience ``{"payload": {...}}`` envelope with no explicit
    ``required_mcp_capabilities`` must still see the manifest
    requirements. Otherwise the bridge would silently drop them.
    """
    payload = {"payload": {"query": "fund:110011"}}
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "news_research",
        "--input", str(input_path),
    ])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    # The manifest requires web_search + financial_news; the bridge
    # must surface them even though the host did not specify them.
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "web_search" in required
    assert "financial_news" in required
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "web_search" in missing
    assert "financial_news" in missing


def test_input_required_mcp_capabilities_adds_extra_requirements(tmp_path: Path) -> None:
    """A host may add extra required capabilities on top of the
    manifest. The union must be honored and the missing list must
    include anything the host added that the host also did not
    supply.
    """
    payload = {
        "payload": {"query": "fund:110011"},
        # Host adds an extra capability the manifest does not require.
        # The host also does not supply mcp_responses for it.
        # We do not supply web_search/financial_news either, so all
        # three are missing.
        "required_mcp_capabilities": ["extra_capability"],
    }
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "news_research",
        "--input", str(input_path),
    ])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    required = set(out["metadata"]["required_mcp_capabilities"])
    assert "extra_capability" in required
    assert "web_search" in required
    assert "financial_news" in required
    missing = set(out["metadata"]["missing_mcp_capabilities"])
    assert "extra_capability" in missing


def test_skill_without_manifest_mcp_requirement_does_not_get_synthetic_missing(
    tmp_path: Path,
) -> None:
    """``fund_analysis`` has no manifest ``requires_mcp``. The bridge
    must not invent missing capabilities just because the host used a
    convenience input.
    """
    payload = {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 100000,
                "cash_available": 10000,
                "positions": [],
            },
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
        },
    }
    input_path = _write_input(tmp_path, payload)
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["metadata"]["required_mcp_capabilities"] == []
    assert out["metadata"]["missing_mcp_capabilities"] == []


def test_emit_envelope_falls_back_to_serialization_failed_envelope(tmp_path: Path) -> None:
    """When the original envelope is not JSON-serializable, the
    bridge must:

    - still write *some* valid JSON to the output target,
    - with ``ok=false`` and ``error.code == JSON_SERIALIZATION_FAILED``,
    - and return exit code 2 (bridge-level failure) even when the
      original envelope had ``ok=true``.
    """
    from src.skillpack import run_skill as bridge

    class Unserializable:
        def __str__(self) -> str:  # pragma: no cover - exercised by json.dumps
            raise TypeError("intentionally unserializable")

    out_path = tmp_path / "out.json"
    bad_envelope = {
        "ok": True,
        "skill_name": "fund_analysis",
        "metadata": {"bogus": Unserializable()},
    }
    rc = bridge._emit_envelope(bad_envelope, pretty=False, output_path=out_path)
    assert rc == 2, (
        f"expected exit code 2 when fallback fires, got {rc}"
    )
    text = out_path.read_text(encoding="utf-8")
    fallback = json.loads(text)
    assert fallback["ok"] is False
    assert fallback["error"]["code"] == "JSON_SERIALIZATION_FAILED"


def test_emit_envelope_serialization_failure_includes_no_traceback_on_stdout(
    tmp_path: Path, capsys,
) -> None:
    """When the fallback fires and ``output_path`` is None, the
    fallback JSON must be the only thing written to stdout. No
    Python traceback may leak to the host.
    """
    from src.skillpack import run_skill as bridge

    class Unserializable:
        def __str__(self) -> str:  # pragma: no cover - exercised by json.dumps
            raise TypeError("intentionally unserializable")

    bad_envelope = {
        "ok": True,
        "metadata": {"bogus": Unserializable()},
    }
    rc = bridge._emit_envelope(bad_envelope, pretty=False, output_path=None)
    assert rc == 2
    captured = capsys.readouterr()
    # stdout is a single JSON line; no Python traceback.
    assert "Traceback" not in captured.out
    fallback = json.loads(captured.out)
    assert fallback["ok"] is False
    assert fallback["error"]["code"] == "JSON_SERIALIZATION_FAILED"
