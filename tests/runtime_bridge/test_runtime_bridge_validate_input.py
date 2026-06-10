"""Runtime bridge structural input validation command tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.skillpack import input_contracts
from tests.support.bridge_runner import run_bridge_inprocess_metadata


ROOT = Path(__file__).resolve().parents[2]
INPUT_CONTRACT_PATH = ROOT / "skillpack" / "input-contracts.yaml"


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


def _validate_input(skill: str, payload: dict) -> dict:
    return run_bridge_inprocess_metadata(
        skill=skill,
        validate_input=True,
        input_data=payload,
        pretty=True,
    )


def test_existing_fund_analysis_example_validates_true() -> None:
    input_text = (ROOT / "examples" / "runtime_bridge_fund_analysis_input.json").read_text(encoding="utf-8")
    out = run_bridge_inprocess_metadata(
        skill="fund_analysis",
        validate_input=True,
        input_text=input_text,
        pretty=True,
    )
    result = out["validation_result"]
    assert out["ok"] is True
    assert result["valid"] is True
    assert result["detected_input_mode"] == "portfolio_snapshot"
    assert "artifacts" not in out
    assert "evidence_items" not in out


def test_minimal_portfolio_snapshot_validates_true() -> None:
    out = _validate_input("fund_analysis", _minimal_portfolio())
    result = out["validation_result"]
    assert result["valid"] is True
    assert result["detected_input_mode"] == "portfolio_snapshot"
    assert "risk_profile" in result["missing_recommended"]
    assert not result["errors"]


def test_transactions_current_nav_as_of_date_validates_true() -> None:
    payload = {
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
    }
    out = _validate_input("fund_analysis", payload)
    result = out["validation_result"]
    assert result["valid"] is True
    assert result["detected_input_mode"] == "ledger_derived"


def test_transactions_current_nav_without_as_of_date_is_invalid() -> None:
    payload = {
        "payload": {
            "transactions": [{"action": "BUY", "fund_code": "110011"}],
            "current_nav": {"110011": 1.2},
        }
    }
    out = _validate_input("fund_analysis", payload)
    result = out["validation_result"]
    assert result["valid"] is False
    assert result["severity"] == "INVALID"
    assert any("as_of_date" in err["message"] for err in result["errors"])


def test_empty_payload_is_invalid_with_clear_error() -> None:
    out = _validate_input("fund_analysis", {"payload": {}})
    result = out["validation_result"]
    assert result["valid"] is False
    assert result["severity"] == "INVALID"
    assert any(err["code"] == "MISSING_MINIMUM_INPUT" for err in result["errors"])


def test_missing_recommended_fields_are_not_hard_errors() -> None:
    out = _validate_input("fund_analysis", _minimal_portfolio())
    result = out["validation_result"]
    assert result["valid"] is True
    assert "risk_profile" in result["missing_recommended"]
    assert any(warn["code"] == "MISSING_RECOMMENDED" for warn in result["warnings"])
    assert not result["errors"]


def test_missing_recommended_and_optional_fields_match_yaml() -> None:
    out = _validate_input("fund_analysis", _minimal_portfolio())
    result = out["validation_result"]
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

    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(_minimal_portfolio()), encoding="utf-8")
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


def test_news_research_validation_reports_missing_mcp() -> None:
    out = _validate_input("news_research", {"payload": {"query": "fund:110011"}})
    result = out["validation_result"]
    assert result["valid"] is False
    assert result["missing_mcp_capabilities"] == ["web_search", "financial_news"]
    assert set(result["capability_coverage"]["missing"]) == {
        "web_search",
        "financial_news",
    }


def test_news_research_validation_accepts_canned_mcp_responses() -> None:
    payload = {
        "payload": {"query": "fund:110011"},
        "mcp_responses": {
            "web_search": {"items": []},
            "financial_news": {"items": []},
        },
    }
    out = _validate_input("news_research", payload)
    result = out["validation_result"]
    assert result["valid"] is True
    assert result["missing_mcp_capabilities"] == []
    assert set(result["capability_coverage"]["present"]) == {
        "web_search",
        "financial_news",
    }
