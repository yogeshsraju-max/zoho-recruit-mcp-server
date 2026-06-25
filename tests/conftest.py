"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        ZOHO_CLIENT_ID="cid",
        ZOHO_CLIENT_SECRET="secret",
        ZOHO_REFRESH_TOKEN="refresh",
        ZOHO_REGION="com",
        MAX_RETRIES=2,
        REQUEST_TIMEOUT_SECONDS=5,
        RATE_LIMIT_PER_MINUTE=1000,
    )


class StubClient:
    """A minimal stand-in for ZohoClient used in domain unit tests.

    Records calls and returns queued responses keyed by (method, path-prefix).
    """

    def __init__(self):
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []
        self._responses: dict[str, dict] = {}

    def queue(self, key: str, response: dict) -> None:
        self._responses[key] = response

    def _lookup(self, method: str, path: str) -> dict:
        for key, resp in self._responses.items():
            m, prefix = key.split(" ", 1)
            if m == method and path.startswith(prefix):
                return resp
        return {"data": []}

    async def get(self, path, params=None):
        self.calls.append(("GET", path, params, None))
        return self._lookup("GET", path)

    async def post(self, path, json=None):
        self.calls.append(("POST", path, None, json))
        return self._lookup("POST", path)

    async def put(self, path, json=None):
        self.calls.append(("PUT", path, None, json))
        return self._lookup("PUT", path)

    async def delete(self, path, params=None):
        self.calls.append(("DELETE", path, params, None))
        return self._lookup("DELETE", path)

    async def aclose(self):
        pass


@pytest.fixture
def stub_client() -> StubClient:
    return StubClient()
