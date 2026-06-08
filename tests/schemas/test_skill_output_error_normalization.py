"""SkillOutput error normalization tests.

Verifies that SkillOutput.errors serialize as canonical SkillError-shaped
dictionaries with code, message, details, and recoverable fields.
"""

from __future__ import annotations

from src.schemas.evidence import EvidenceItem
from src.schemas.skill import (
    SkillError,
    SkillOutput,
    make_skill_error_dict,
    normalize_skill_error,
    normalize_skill_errors,
)


class TestNormalizeSkillError:
    def test_skill_error_object_normalized(self):
        err = SkillError(code="INVALID_INPUT", message="bad payload", details={"k": 1}, recoverable=False)
        result = normalize_skill_error(err)
        assert result == {
            "code": "INVALID_INPUT",
            "message": "bad payload",
            "details": {"k": 1},
            "recoverable": False,
        }

    def test_dict_with_all_fields_preserved(self):
        d = {"code": "MCP_CALL_FAILED", "message": "timeout", "details": {"cap": "x"}, "recoverable": False}
        result = normalize_skill_error(d)
        assert result == d

    def test_dict_missing_recoverable_gets_default(self):
        d = {"code": "EMPTY_RESULT", "message": "no items", "details": {}}
        result = normalize_skill_error(d)
        assert result["recoverable"] is True

    def test_dict_missing_details_gets_empty_dict(self):
        d = {"code": "INTERNAL_ERROR", "message": "oops", "recoverable": True}
        result = normalize_skill_error(d)
        assert result["details"] == {}

    def test_dict_missing_code_gets_default(self):
        d = {"message": "something went wrong"}
        result = normalize_skill_error(d)
        assert result["code"] == "RUNTIME_ERROR"
        assert result["message"] == "something went wrong"

    def test_dict_missing_message_stringifies(self):
        d = {"code": "X"}
        result = normalize_skill_error(d)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_dict_non_dict_details_wrapped(self):
        d = {"code": "X", "message": "m", "details": "not a dict"}
        result = normalize_skill_error(d)
        assert result["details"] == {"raw_details": "not a dict"}

    def test_dict_non_bool_recoverable_defaults_true(self):
        d = {"code": "X", "message": "m", "recoverable": "yes"}
        result = normalize_skill_error(d)
        assert result["recoverable"] is True

    def test_string_error_gets_default_code(self):
        result = normalize_skill_error("something broke")
        assert result == {
            "code": "RUNTIME_ERROR",
            "message": "something broke",
            "details": {},
            "recoverable": True,
        }

    def test_string_error_custom_default_code(self):
        result = normalize_skill_error("fail", default_code="CUSTOM")
        assert result["code"] == "CUSTOM"

    def test_unknown_type_stringified(self):
        result = normalize_skill_error(42)
        assert result["code"] == "RUNTIME_ERROR"
        assert result["message"] == "42"
        assert result["details"] == {"raw_type": "int"}
        assert result["recoverable"] is True


class TestNormalizeSkillErrors:
    def test_none_returns_empty_list(self):
        assert normalize_skill_errors(None) == []

    def test_empty_list_returns_empty_list(self):
        assert normalize_skill_errors([]) == []

    def test_mixed_types_normalized(self):
        errors = [
            SkillError(code="A", message="a"),
            {"code": "B", "message": "b"},
            "string error",
        ]
        result = normalize_skill_errors(errors)
        assert len(result) == 3
        for r in result:
            assert "code" in r
            assert "message" in r
            assert "details" in r
            assert "recoverable" in r
        assert result[0]["code"] == "A"
        assert result[1]["code"] == "B"
        assert result[2]["code"] == "RUNTIME_ERROR"


class TestMakeSkillErrorDict:
    def test_basic(self):
        result = make_skill_error_dict("CODE", "msg")
        assert result == {"code": "CODE", "message": "msg", "details": {}, "recoverable": True}

    def test_with_details_and_recoverable(self):
        result = make_skill_error_dict("CODE", "msg", details={"k": 1}, recoverable=False)
        assert result == {"code": "CODE", "message": "msg", "details": {"k": 1}, "recoverable": False}


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
