"""Tests for privacy-safe logging utilities."""

from src.skills_runtime.common.logging import redact_pii, PrivacySafeFormatter, get_skill_logger


class TestRedactPii:
    def test_redacts_monetary_amounts(self):
        result = redact_pii("amount=12345.67")
        assert "12345.67" not in result
        assert "amount=***" in result

    def test_redacts_monetary_value(self):
        result = redact_pii("value: 10000")
        assert "10000" not in result
        assert "value=***" in result

    def test_preserves_fund_codes(self):
        result = redact_pii("fund_code=110011")
        assert "110011" in result

    def test_redacts_personal_name(self):
        result = redact_pii("name=Zhang San")
        assert "Zhang San" not in result
        assert "name=***" in result

    def test_redacts_email(self):
        result = redact_pii("email=user@example.com")
        assert "user@example.com" not in result
        assert "email=***" in result

    def test_preserves_non_pii(self):
        result = redact_pii("skill=fund_analysis status=OK")
        assert "fund_analysis" in result
        assert "OK" in result

    def test_empty_string(self):
        assert redact_pii("") == ""


class TestGetSkillLogger:
    def test_returns_logger(self):
        logger = get_skill_logger("test_skill")
        assert logger.name == "test_skill"

    def test_default_logger_name(self):
        logger = get_skill_logger()
        assert logger.name == "fund_agent.skill"
