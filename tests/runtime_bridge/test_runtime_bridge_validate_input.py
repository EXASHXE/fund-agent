"""Runtime bridge structural input validation command tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.skillpack import input_contracts


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
INPUT_CONTRACT_PATH = ROOT / "skillpack" / "input-contracts.yaml"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _json(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip(), f"stdout must contain JSON, stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


def _fund_input_contract() -> dict:
    data = yaml.safe_load(INPUT_CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def _recommended_keys() -> list[str]:
    return [item["key"] for item in _fund_input_contract()["recommended_fields"]]


def _optional_keys() -> list[str]:
    return [item["key"] for item in _fund_input_contract()["optional_fields"]]


def _minimal_portfolio() -> dict:
    return {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "positions": [
                    {
                        "fund_code": "110011",
                        "current_value": 30000,
                    }
                ],
            }
        }
    }


def test_existing_fund_analysis_example_validates_true() -> None:
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        "examples/runtime_bridge_fund_analysis_input.json",
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    result = out["validation_result"]
    assert out["ok"] is True
    assert result["valid"] is True
    assert result["detected_input_mode"] == "portfolio_snapshot"
    assert "artifacts" not in out
    assert "evidence_items" not in out


def test_minimal_portfolio_snapshot_validates_true(tmp_path: Path) -> None:
    input_path = _write(tmp_path, _minimal_portfolio())
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is True
    assert result["detected_input_mode"] == "portfolio_snapshot"
    assert "risk_profile" in result["missing_recommended"]
    assert not result["errors"]


def test_transactions_current_nav_as_of_date_validates_true(tmp_path: Path) -> None:
    input_path = _write(
        tmp_path,
        {
            "payload": {
                "as_of_date": "2026-06-01",
                "transactions": [
                    {
                        "action": "BUY",
                        "fund_code": "110011",
                        "date": "2026-01-01",
                        "amount": 10000,
                        "shares": 10000,
                    }
                ],
                "current_nav": {"110011": 1.2},
            }
        },
    )
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is True
    assert result["detected_input_mode"] == "ledger_derived"


def test_transactions_current_nav_without_as_of_date_is_invalid(tmp_path: Path) -> None:
    input_path = _write(
        tmp_path,
        {
            "payload": {
                "transactions": [{"action": "BUY", "fund_code": "110011"}],
                "current_nav": {"110011": 1.2},
            }
        },
    )
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is False
    assert result["severity"] == "INVALID"
    assert any("as_of_date" in err["message"] for err in result["errors"])


def test_empty_payload_is_invalid_with_clear_error(tmp_path: Path) -> None:
    input_path = _write(tmp_path, {"payload": {}})
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is False
    assert result["severity"] == "INVALID"
    assert any(err["code"] == "MISSING_MINIMUM_INPUT" for err in result["errors"])


def test_missing_recommended_fields_are_not_hard_errors(tmp_path: Path) -> None:
    input_path = _write(tmp_path, _minimal_portfolio())
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is True
    assert "risk_profile" in result["missing_recommended"]
    assert any(warn["code"] == "MISSING_RECOMMENDED" for warn in result["warnings"])
    assert not result["errors"]


def test_missing_recommended_and_optional_fields_match_yaml(tmp_path: Path) -> None:
    input_path = _write(tmp_path, _minimal_portfolio())
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(input_path),
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is True
    assert set(result["missing_recommended"]) == set(_recommended_keys())
    assert set(result["missing_optional"]) == set(_optional_keys())
    assert not result["errors"]


def test_validate_input_field_lists_are_contract_loader_driven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_contract = {
        "recommended_fields": [
            {"key": "fake_recommended", "description": "fake", "missing_behavior": "warning"}
        ],
        "optional_fields": [
            {"key": "fake_optional", "description": "fake", "missing_behavior": "missing"}
        ],
        "host_data_capability_fields": {
            "portfolio_snapshot": {"payload_fields": ["fake_portfolio"]}
        },
    }

    monkeypatch.setattr(
        input_contracts,
        "get_skill_input_contract",
        lambda _skill_id, _path: fake_contract,
    )

    result = input_contracts.validate_skill_input("fund_analysis", _minimal_portfolio())
    validation = result["validation_result"]
    assert validation["valid"] is True
    assert validation["missing_recommended"] == ["fake_recommended"]
    assert validation["missing_optional"] == ["fake_optional"]
    assert any(
        warn["code"] == "MISSING_RECOMMENDED"
        and warn["path"] == "payload.fake_recommended"
        for warn in validation["warnings"]
    )
    assert "portfolio_snapshot" in validation["capability_coverage"]["missing"]


def test_validate_input_does_not_import_or_run_fund_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.skillpack import run_skill as bridge

    def fail_resolve_runtime(runtime_path: str) -> object:
        raise AssertionError(f"runtime import should not happen: {runtime_path}")

    input_path = _write(tmp_path, _minimal_portfolio())
    monkeypatch.setattr(bridge, "resolve_runtime", fail_resolve_runtime)
    rc = bridge.run_bridge(
        skill_name="fund_analysis",
        input_path=str(input_path),
        validate_input=True,
        pretty=True,
    )
    captured = capsys.readouterr()
    assert rc == 0
    out = json.loads(captured.out)
    assert out["ok"] is True
    assert out["validation_result"]["valid"] is True
    assert "artifacts" not in out
    assert "evidence_items" not in out


def test_news_research_validation_reports_missing_mcp(tmp_path: Path) -> None:
    input_path = _write(tmp_path, {"payload": {"query": "fund:110011"}})
    proc = _run([
        "--skill",
        "news_research",
        "--input",
        str(input_path),
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is False
    assert result["missing_mcp_capabilities"] == ["web_search", "financial_news"]
    assert set(result["capability_coverage"]["missing"]) == {
        "web_search",
        "financial_news",
    }


def test_news_research_validation_accepts_canned_mcp_responses(tmp_path: Path) -> None:
    input_path = _write(
        tmp_path,
        {
            "payload": {"query": "fund:110011"},
            "mcp_responses": {
                "web_search": {"items": []},
                "financial_news": {"items": []},
            },
        },
    )
    proc = _run([
        "--skill",
        "news_research",
        "--input",
        str(input_path),
        "--validate-input",
    ])
    assert proc.returncode == 0, proc.stderr
    result = _json(proc)["validation_result"]
    assert result["valid"] is True
    assert result["missing_mcp_capabilities"] == []
    assert set(result["capability_coverage"]["present"]) == {
        "web_search",
        "financial_news",
    }
