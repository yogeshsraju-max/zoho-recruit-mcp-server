"""Error handling: a small taxonomy of errors plus helpers that turn any
exception into a stable, machine-readable MCP error payload.

Tools should return the dict produced by ``to_mcp_error`` (or raise
``ZohoError`` and let the decorator handle it) so Claude always receives a
consistent ``{"error_code": ..., "message": ...}`` shape.
"""

from __future__ import annotations

import functools
import inspect
import time
from typing import Any, Awaitable, Callable

from .logger import bind_context


class ErrorCode:
    """Stable error codes surfaced to the MCP client."""

    TOKEN_EXPIRED = "ZOHO_TOKEN_EXPIRED"
    AUTH_FAILED = "ZOHO_AUTH_FAILED"
    RATE_LIMITED = "ZOHO_RATE_LIMITED"
    NOT_FOUND = "ZOHO_RECORD_NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    API_ERROR = "ZOHO_API_ERROR"
    NOT_CONFIGURED = "ENDPOINT_NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN_ERROR"


class ZohoError(Exception):
    """Base class for all errors raised inside the server."""

    error_code: str = ErrorCode.UNKNOWN

    def __init__(self, message: str, *, details: Any = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if error_code:
            self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class TokenExpiredError(ZohoError):
    error_code = ErrorCode.TOKEN_EXPIRED


class AuthError(ZohoError):
    error_code = ErrorCode.AUTH_FAILED


class RateLimitError(ZohoError):
    error_code = ErrorCode.RATE_LIMITED


class NotFoundError(ZohoError):
    error_code = ErrorCode.NOT_FOUND


class InvalidInputError(ZohoError):
    error_code = ErrorCode.INVALID_INPUT


class NetworkError(ZohoError):
    error_code = ErrorCode.NETWORK_ERROR


class ApiError(ZohoError):
    error_code = ErrorCode.API_ERROR


class NotConfiguredError(ZohoError):
    error_code = ErrorCode.NOT_CONFIGURED


def to_mcp_error(exc: Exception) -> dict[str, Any]:
    """Convert any exception into a stable MCP error dict."""
    if isinstance(exc, ZohoError):
        return exc.to_dict()
    return {
        "error_code": ErrorCode.UNKNOWN,
        "message": str(exc) or exc.__class__.__name__,
    }


def tool_handler(name: str) -> Callable:
    """Decorator for MCP tool coroutines.

    Adds: request-id binding, execution timing, structured logging, and uniform
    error translation. The wrapped function may return any JSON-serialisable
    value; on failure a stable error dict is returned instead of raising, so the
    MCP client always gets a well-formed result.
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"tool_handler expects an async function, got {func!r}")

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = bind_context(tool=name)
            start = time.perf_counter()
            log.info("tool invoked")
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                log.info("tool ok in {:.0f}ms", elapsed)
                return result
            except ZohoError as exc:
                elapsed = (time.perf_counter() - start) * 1000
                log.warning(
                    "tool failed [{}] in {:.0f}ms: {}",
                    exc.error_code,
                    elapsed,
                    exc.message,
                )
                return exc.to_dict()
            except Exception as exc:  # noqa: BLE001 - top-level safety net
                elapsed = (time.perf_counter() - start) * 1000
                log.exception("tool crashed in {:.0f}ms", elapsed)
                return to_mcp_error(exc)

        return wrapper

    return decorator


__all__ = [
    "ErrorCode",
    "ZohoError",
    "TokenExpiredError",
    "AuthError",
    "RateLimitError",
    "NotFoundError",
    "InvalidInputError",
    "NetworkError",
    "ApiError",
    "NotConfiguredError",
    "to_mcp_error",
    "tool_handler",
]
