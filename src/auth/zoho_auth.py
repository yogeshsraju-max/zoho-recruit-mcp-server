"""Zoho OAuth 2.0 token management.

Zoho's server-based OAuth flow issues a long-lived *refresh token* once (during
setup). At runtime the server exchanges that refresh token for short-lived
*access tokens* (valid ~1 hour) and caches them until shortly before expiry.

This module is responsible only for producing a valid access token. It is
concurrency-safe: simultaneous callers share a single in-flight refresh.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..utils.error_handler import AuthError, NetworkError, TokenExpiredError
from ..utils.logger import logger

# Refresh this many seconds before the real expiry to avoid edge races.
_EXPIRY_SKEW_SECONDS = 120


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float  # monotonic-ish wall clock (time.time)

    def is_valid(self) -> bool:
        return bool(self.access_token) and time.time() < (
            self.expires_at - _EXPIRY_SKEW_SECONDS
        )


class ZohoAuth:
    """Manages access-token lifecycle from a configured refresh token."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = http_client
        self._owns_client = http_client is None
        self._cache: _CachedToken | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.request_timeout_seconds
            )
        return self._client

    async def get_access_token(self, force_refresh: bool = False) -> str:
        """Return a valid access token, refreshing if necessary."""
        if not force_refresh and self._cache and self._cache.is_valid():
            return self._cache.access_token

        async with self._lock:
            # Re-check inside the lock: another coroutine may have refreshed.
            if not force_refresh and self._cache and self._cache.is_valid():
                return self._cache.access_token
            return await self._refresh()

    async def invalidate(self) -> None:
        """Drop the cached token (call after a 401 to force a refresh)."""
        async with self._lock:
            self._cache = None

    async def _refresh(self) -> str:
        if not self._settings.has_credentials():
            raise AuthError(
                "Missing Zoho OAuth credentials. Set ZOHO_CLIENT_ID, "
                "ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN."
            )

        client = await self._get_client()
        params = {
            "grant_type": "refresh_token",
            "client_id": self._settings.zoho_client_id,
            "client_secret": self._settings.zoho_client_secret,
            "refresh_token": self._settings.zoho_refresh_token,
        }
        logger.bind(tool="auth").info("refreshing access token")
        try:
            # Zoho expects these as query/form params on a POST.
            resp = await client.post(self._settings.token_endpoint, data=params)
        except httpx.HTTPError as exc:
            raise NetworkError(f"Network error contacting Zoho accounts: {exc}") from exc

        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}

        if resp.status_code != 200 or "access_token" not in body:
            # Zoho returns 200 with an "error" key for some failures.
            err = body.get("error") if isinstance(body, dict) else None
            if err in {"invalid_code", "invalid_token", "invalid_grant"}:
                raise TokenExpiredError(
                    "Refresh token is invalid or revoked. Re-authorise the app "
                    "and update ZOHO_REFRESH_TOKEN.",
                    details={"zoho_error": err},
                )
            raise AuthError(
                "Failed to obtain access token from Zoho.",
                details={"status": resp.status_code, "zoho_error": err or body},
            )

        access_token = body["access_token"]
        # Zoho returns expires_in in seconds (typically 3600).
        expires_in = float(body.get("expires_in", 3600))
        self._cache = _CachedToken(
            access_token=access_token,
            expires_at=time.time() + expires_in,
        )
        logger.bind(tool="auth").info("access token refreshed (ttl={}s)", int(expires_in))
        return access_token

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
