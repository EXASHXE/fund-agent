"""SkillError contract tests.

Verifies that SkillError.to_dict() produces canonical error objects,
that normalize_skill_error handles all input types correctly, and that
normalize_skill_errors and make_skill_error_dict behave as expected.
"""

from __future__ import annotations

from src.schemas.skill import (
    SkillError,
    make_skill_error_dict,
    normalize_skill_error,
    normalize_skill_errors,
)


class TestSkillErrorToDict:
    def test_includes_all_canonical_fields(self):
        err = SkillError(code="TEST_CODE", message="test message")
        d = err.to_dict()
        assert d == {
            "code": "TEST_CODE",
            "message": "test message",
            "details": {},
            "recoverable": True,
        }

    def test_details_defaults_to_empty_dict(self):
        err = SkillError(code="X", message="m")
        assert err.to_dict()["details"] == {}

    def test_recoverable_defaults_to_true(self):
        err = SkillError(code="X", message="m")
        assert err.to_dict()["recoverable"] is True

    def test_recoverable_false_preserved(self):
        err = SkillError(code="X", message="m", recoverable=False)
        assert err.to_dict()["recoverable"] is False

    def test_details_populated(self):
        err = SkillError(code="X", message="m", details={"k": 1})
        assert err.to_dict()["details"] == {"k": 1}


class TestNormalizeSkillErrorSkillErrorInput:
    def test_skill_error_object_normalized(self):
        err = SkillError(code="INVALID_INPUT", message="bad payload", details={"k": 1}, recoverable=False)
        result = normalize_skill_error(err)
        assert result == {
            "code": "INVALID_INPUT",
            "message": "bad payload",
            "details": {"k": 1},
            "recoverable": False,
        }


class TestNormalizeSkillErrorDictInput:
    def test_dict_with_all_fields_preserved(self):
        d = {"code": "MCP_CALL_FAILED", "message": "timeout", "details": {"cap": "x"}, "recoverable": False}
        result = normalize_skill_error(d)
        assert result == d

    def test_dict_missing_recoverable_gets_default(self):
        d = {"code": "EMPTY_RESULT", "message": "no items", "details": {}}
        result = normalize_skill_error(d)
        assert result["recoverable"] is True

    def test_dict_missing_recoverable_uses_param_default(self):
        d = {"code": "X", "message": "m", "details": {}}
        result = normalize_skill_error(d, recoverable=False)
        assert result["recoverable"] is False

    def test_dict_with_invalid_recoverable_uses_param_default(self):
        d = {"code": "X", "message": "m", "details": {}, "recoverable": "yes"}
        result = normalize_skill_error(d, recoverable=False)
        assert result["recoverable"] is False

    def test_dict_with_valid_recoverable_preserved(self):
        d = {"code": "X", "message": "m", "details": {}, "recoverable": True}
        result = normalize_skill_error(d, recoverable=False)
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


class TestNormalizeSkillErrorStringInput:
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


class TestNormalizeSkillErrorExceptionInput:
    def test_exception_gets_code_message_details_recoverable(self):
        exc = ValueError("bad value")
        result = normalize_skill_error(exc)
        assert result["code"] == "RUNTIME_ERROR"
        assert result["message"] == "bad value"
        assert result["details"] == {"exception_type": "ValueError"}
        assert result["recoverable"] is True

    def test_exception_custom_default_code(self):
        exc = RuntimeError("boom")
        result = normalize_skill_error(exc, default_code="INTERNAL_ERROR")
        assert result["code"] == "INTERNAL_ERROR"

    def test_exception_custom_recoverable(self):
        exc = TypeError("wrong type")
        result = normalize_skill_error(exc, recoverable=False)
        assert result["recoverable"] is False


class TestNormalizeSkillErrorUnknownInput:
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

    def test_preserves_order(self):
        errors = [
            SkillError(code="FIRST", message="first"),
            {"code": "SECOND", "message": "second"},
            "third",
            ValueError("fourth"),
        ]
        result = normalize_skill_errors(errors)
        assert len(result) == 4
        assert result[0]["code"] == "FIRST"
        assert result[1]["code"] == "SECOND"
        assert result[2]["code"] == "RUNTIME_ERROR"
        assert result[3]["code"] == "RUNTIME_ERROR"
        assert result[3]["details"] == {"exception_type": "ValueError"}

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
