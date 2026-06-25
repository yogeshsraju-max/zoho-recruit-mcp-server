"""Structured logging built on loguru.

Provides:
  * configure_logging() to set up a JSON-ish structured sink.
  * A redaction patcher that strips secrets (tokens, passwords) and common PII
    fields from log records so they never reach the sink.
  * request-id binding helpers for per-tool-call correlation.

Never log: access/refresh tokens, client secrets, passwords, candidate emails,
phone numbers, or resume contents.
"""

from __future__ import annotations

import re
import sys
import uuid
from typing import Any

from loguru import logger

# Keys whose values must always be masked if they appear in structured "extra".
_SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "password",
    "token",
    "email",
    "phone",
    "mobile",
    "resume",
    "resume_text",
}

# Regexes that scrub secrets accidentally embedded in free-text messages.
_TOKEN_PATTERNS = [
    re.compile(r"(Zoho-oauthtoken\s+)[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(refresh_token=)[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(client_secret=)[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(access_token\"?\s*[:=]\s*\"?)[A-Za-z0-9._-]+", re.IGNORECASE),
]

_MASK = "***REDACTED***"


def _scrub_text(message: str) -> str:
    for pattern in _TOKEN_PATTERNS:
        message = pattern.sub(rf"\1{_MASK}", message)
    return message


def _redact_record(record: dict[str, Any]) -> None:
    """Mutate a loguru record in place to remove sensitive content."""
    record["message"] = _scrub_text(record["message"])
    extra = record.get("extra", {})
    for key in list(extra.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            extra[key] = _MASK


def configure_logging(level: str = "INFO") -> None:
    """Configure the global logger. Idempotent."""
    logger.remove()
    logger.configure(patcher=_redact_record)
    logger.add(
        sys.stderr,  # stderr keeps stdout clean for the STDIO MCP transport
        level=level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "req=<cyan>{extra[request_id]}</cyan> "
            "tool=<magenta>{extra[tool]}</magenta> | "
            "<level>{message}</level>"
        ),
    )
    # Ensure the bound keys always exist so the format string never errors.
    logger.configure(extra={"request_id": "-", "tool": "-"})


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def bind_context(tool: str, request_id: str | None = None):
    """Return a logger bound to a tool name and request id."""
    return logger.bind(tool=tool, request_id=request_id or new_request_id())


__all__ = ["logger", "configure_logging", "new_request_id", "bind_context"]
