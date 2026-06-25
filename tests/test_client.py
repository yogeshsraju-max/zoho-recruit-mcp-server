"""Tests for the ZohoClient HTTP layer."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.utils.error_handler import ApiError, NotFoundError
from src.zoho.client import ZohoClient


def _token_route(settings):
    return respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "expires_in": 3600}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_get_injects_auth_header(settings):
    _token_route(settings)
    captured = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    respx.get(f"{settings.zoho_base_url}/Candidates").mock(side_effect=responder)

    client = ZohoClient(settings)
    resp = await client.get("/Candidates")
    assert resp["data"][0]["id"] == "1"
    assert captured["auth"] == "Zoho-oauthtoken tok"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_500_then_success(settings):
    _token_route(settings)
    route = respx.get(f"{settings.zoho_base_url}/Candidates").mock(
        side_effect=[
            httpx.Response(500, json={"error": "boom"}),
            httpx.Response(200, json={"data": [{"id": "ok"}]}),
        ]
    )
    client = ZohoClient(settings)
    resp = await client.get("/Candidates")
    assert resp["data"][0]["id"] == "ok"
    assert route.call_count == 2
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_401_triggers_refresh_and_retry(settings):
    token_route = _token_route(settings)
    route = respx.get(f"{settings.zoho_base_url}/Candidates").mock(
        side_effect=[
            httpx.Response(401, json={"error": "expired"}),
            httpx.Response(200, json={"data": [{"id": "after-refresh"}]}),
        ]
    )
    client = ZohoClient(settings)
    resp = await client.get("/Candidates")
    assert resp["data"][0]["id"] == "after-refresh"
    assert route.call_count == 2
    assert token_route.call_count == 2  # initial + forced refresh
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_404_maps_to_not_found(settings):
    _token_route(settings)
    respx.get(f"{settings.zoho_base_url}/Candidates/999").mock(
        return_value=httpx.Response(404, json={})
    )
    client = ZohoClient(settings)
    with pytest.raises(NotFoundError):
        await client.get("/Candidates/999")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_400_maps_to_api_error(settings):
    _token_route(settings)
    respx.post(f"{settings.zoho_base_url}/Candidates").mock(
        return_value=httpx.Response(400, json={"code": "INVALID_DATA"})
    )
    client = ZohoClient(settings)
    with pytest.raises(ApiError):
        await client.post("/Candidates", json={"data": [{}]})
    await client.aclose()
