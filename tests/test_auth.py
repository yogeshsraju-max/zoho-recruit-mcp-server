"""Tests for ZohoAuth token lifecycle."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.auth.zoho_auth import ZohoAuth
from src.utils.error_handler import TokenExpiredError


@pytest.mark.asyncio
@respx.mock
async def test_refresh_returns_access_token(settings):
    route = respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(
            200, json={"access_token": "abc123", "expires_in": 3600}
        )
    )
    auth = ZohoAuth(settings)
    token = await auth.get_access_token()
    assert token == "abc123"
    assert route.called
    await auth.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_token_is_cached(settings):
    route = respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(
            200, json={"access_token": "cached", "expires_in": 3600}
        )
    )
    auth = ZohoAuth(settings)
    t1 = await auth.get_access_token()
    t2 = await auth.get_access_token()
    assert t1 == t2 == "cached"
    assert route.call_count == 1  # second call served from cache
    await auth.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_invalid_refresh_token_raises(settings):
    respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(200, json={"error": "invalid_grant"})
    )
    auth = ZohoAuth(settings)
    with pytest.raises(TokenExpiredError):
        await auth.get_access_token()
    await auth.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_force_refresh_bypasses_cache(settings):
    route = respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(
            200, json={"access_token": "fresh", "expires_in": 3600}
        )
    )
    auth = ZohoAuth(settings)
    await auth.get_access_token()
    await auth.get_access_token(force_refresh=True)
    assert route.call_count == 2
    await auth.aclose()
