"""SkillOutput error normalization tests.

Verifies that SkillOutput.errors serialize as canonical SkillError-shaped
dictionaries with code, message, details, and recoverable fields.
"""

from __future__ import annotations

from src.schemas.skill import (
    SkillError,
    SkillOutput,
)


class TestSkillOutputErrorNormalization:
    def test_skill_error_object_in_errors(self):
        err = SkillError(code="INVALID_INPUT", message="bad", recoverable=False)
        output = SkillOutput(errors=[err])
        d = output.to_dict()
        assert len(d["errors"]) == 1
        assert d["errors"][0] == {"code": "INVALID_INPUT", "message": "bad", "details": {}, "recoverable": False}

    def test_dict_missing_recoverable_in_errors(self):
        output = SkillOutput(errors=[{"code": "X", "message": "m", "details": {}}])
        d = output.to_dict()
        assert d["errors"][0]["recoverable"] is True

    def test_dict_missing_details_in_errors(self):
        output = SkillOutput(errors=[{"code": "X", "message": "m", "recoverable": True}])
        d = output.to_dict()
        assert d["errors"][0]["details"] == {}

    def test_string_error_in_errors(self):
        output = SkillOutput(errors=["something failed"])
        d = output.to_dict()
        assert d["errors"][0]["code"] == "RUNTIME_ERROR"
        assert d["errors"][0]["message"] == "something failed"
        assert d["errors"][0]["recoverable"] is True

    def test_no_errors_produces_empty_list(self):
        output = SkillOutput()
        d = output.to_dict()
        assert d["errors"] == []

    def test_all_errors_are_canonical_dicts(self):
        errors = [
            SkillError(code="A", message="a"),
            {"code": "B", "message": "b"},
            "string",
        ]
        output = SkillOutput(errors=errors)
        d = output.to_dict()
        for err in d["errors"]:
            assert isinstance(err, dict)
            assert "code" in err
            assert "message" in err
            assert "details" in err
            assert "recoverable" in err
            assert isinstance(err["details"], dict)
            assert isinstance(err["recoverable"], bool)

    def test_status_validation_rejects_invalid(self):
        import pytest
        with pytest.raises(ValueError):
            SkillOutput(status="INVALID")

    def test_preserves_artifacts_evidence_warnings(self):
        from src.schemas.evidence import EvidenceItem
        from datetime import datetime
        ev = EvidenceItem(
            evidence_id="ev-1",
            evidence_type="HardEvidence",
            source_type="test",
            timestamp=datetime.now(),
            related_entities=["fund:001"],
            claim="test claim",
            value={},
        )
        output = SkillOutput(
            artifacts={"report": {"sections": []}},
            evidence_items=[ev],
            warnings=["partial data"],
            status="PARTIAL",
        )
        d = output.to_dict()
        assert d["artifacts"] == {"report": {"sections": []}}
        assert len(d["evidence_items"]) == 1
        assert d["warnings"] == ["partial data"]
        assert d["status"] == "PARTIAL"
