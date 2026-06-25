"""Low-level async HTTP client for the Zoho Recruit API v2.

Responsibilities:
  * Inject the ``Authorization: Zoho-oauthtoken <token>`` header.
  * Transparently refresh + retry once on a 401.
  * Retry transient failures (429 / 5xx / network) with exponential backoff.
  * Apply a simple client-side rate limiter.
  * Map Zoho responses/errors onto the project's error taxonomy.

Higher-level domain modules (candidates, jobs, ...) build on top of this.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..auth.zoho_auth import ZohoAuth
from ..config import Settings
from ..utils.error_handler import (
    ApiError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from ..utils.logger import logger


class _RetryableError(Exception):
    """Internal marker so tenacity only retries the right failures."""


class _AsyncRateLimiter:
    """Sliding-window limiter: at most ``max_calls`` per 60 seconds."""

    def __init__(self, max_calls: int):
        self._max = max(1, max_calls)
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            window_start = now - 60.0
            while self._calls and self._calls[0] < window_start:
                self._calls.popleft()
            if len(self._calls) >= self._max:
                sleep_for = 60.0 - (now - self._calls[0])
                logger.bind(tool="client").warning(
                    "client rate limit hit; sleeping {:.2f}s", sleep_for
                )
                await asyncio.sleep(max(0.0, sleep_for))
            self._calls.append(time.monotonic())


class ZohoClient:
    """Thin async wrapper over the Zoho Recruit REST API."""

    def __init__(self, settings: Settings, auth: ZohoAuth | None = None):
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.zoho_base_url,
            timeout=settings.request_timeout_seconds,
        )
        self._auth = auth or ZohoAuth(settings, http_client=self._http)
        self._limiter = _AsyncRateLimiter(settings.rate_limit_per_minute)

    # -- public surface ------------------------------------------------------

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("DELETE", path, params=params)

    async def aclose(self) -> None:
        await self._auth.aclose()
        await self._http.aclose()

    # -- internals -----------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a request with retry, then 401-refresh-and-retry once."""

        @retry(
            reraise=True,
            stop=stop_after_attempt(self._settings.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception_type((_RetryableError,)),
        )
        async def _attempt(token: str) -> httpx.Response:
            await self._limiter.acquire()
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Content-Type": "application/json",
            }
            try:
                resp = await self._http.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise _RetryableError(f"network error: {exc}") from exc

            if resp.status_code in (429,) or 500 <= resp.status_code < 600:
                raise _RetryableError(
                    f"transient HTTP {resp.status_code} from Zoho"
                )
            return resp

        token = await self._auth.get_access_token()
        try:
            resp = await _attempt(token)
        except _RetryableError as exc:
            msg = str(exc)
            if "network error" in msg:
                raise NetworkError(msg) from exc
            raise RateLimitError(
                "Zoho API is rate limiting or unavailable after retries.",
                details=msg,
            ) from exc

        # Recover once from an expired/invalid access token.
        if resp.status_code == 401:
            logger.bind(tool="client").info("401 received; refreshing token and retrying")
            await self._auth.invalidate()
            token = await self._auth.get_access_token(force_refresh=True)
            try:
                resp = await _attempt(token)
            except _RetryableError as exc:
                raise NetworkError(str(exc)) from exc

        return self._handle_response(method, path, resp)

    def _handle_response(
        self, method: str, path: str, resp: httpx.Response
    ) -> dict[str, Any]:
        # 204 / 202 with no body are valid (e.g. deletes).
        if resp.status_code in (200, 201, 202):
            if not resp.content:
                return {"status": "success"}
            try:
                return resp.json()
            except ValueError:
                return {"status": "success", "raw": resp.text}

        if resp.status_code == 204:
            return {"status": "success"}

        if resp.status_code == 404:
            raise NotFoundError(f"Zoho resource not found: {path}")

        if resp.status_code == 401:
            raise ApiError(
                "Unauthorized after token refresh. Check OAuth scopes.",
                details={"status": 401},
            )

        # Anything else: surface Zoho's structured error if present.
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        raise ApiError(
            f"Zoho API error on {method} {path}",
            details={"status": resp.status_code, "body": body},
        )
