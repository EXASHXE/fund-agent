"""Privacy-safe logging utilities for skill runtime handlers.

Provides a module-level logger with PII redaction patterns.
This module is created but NOT wired into any skill run() methods.
Skills may opt-in to use it in future versions.

Rules:
- Fund codes are kept as-is (not PII)
- Monetary amounts are redacted to "***"
- Personal identifiers (names, IDs) are redacted
- Log level defaults to WARNING to avoid noise
"""

from __future__ import annotations

import logging
import re
from typing import Any


# PII redaction patterns
_MONETARY_PATTERN = re.compile(
    r"(amount|value|cost|price|nav|total|balance|profit|loss|gain|fee)"
    r"['\"]?\s*[:=]\s*['\"]?\d+[\d.,]*",
    re.IGNORECASE,
)
_MONETARY_REPLACEMENT = r"\1=***"

_PERSONAL_ID_PATTERN = re.compile(
    r"(name|id_card|phone|email|address|account)"
    r"['\"]?\s*[:=]\s*['\"]?[\w\-@.]+",
    re.IGNORECASE,
)
_PERSONAL_ID_REPLACEMENT = r"\1=***"


def redact_pii(message: str) -> str:
    """Redact PII from a log message string."""
    message = _MONETARY_PATTERN.sub(_MONETARY_REPLACEMENT, message)
    message = _PERSONAL_ID_PATTERN.sub(_PERSONAL_ID_REPLACEMENT, message)
    return message


class PrivacySafeFormatter(logging.Formatter):
    """Log formatter that redacts PII from log messages."""

    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact_pii(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_pii(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_pii(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return super().format(record)


def get_skill_logger(name: str = "fund_agent.skill") -> logging.Logger:
    """Get a privacy-safe logger for skill runtime use.

    Args:
        name: Logger name, defaults to "fund_agent.skill".

    Returns:
        Configured logger with PII-redacting formatter.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(PrivacySafeFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
    return logger
