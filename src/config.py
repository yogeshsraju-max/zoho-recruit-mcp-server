"""Application configuration.

Loads settings from environment variables (and an optional .env file) using
pydantic-settings. Also resolves the correct Zoho Accounts (OAuth) and Zoho
Recruit (data) base URLs from the configured data-center region.

Region -> domain mapping is based on Zoho's published multi-DC domains. If your
account lives behind a custom or future domain, set ZOHO_BASE_URL and
ZOHO_ACCOUNTS_URL explicitly to override the derived values.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Region configuration ---------------------------------------------------
# Maps the short region code used in ZOHO_REGION to the Zoho top-level domain
# used for both the accounts (OAuth) host and the recruit (API) host.
#
#   accounts host : https://accounts.zoho.<domain>
#   recruit host  : https://recruit.zoho.<domain>/recruit/v2
#
# Canada is special-cased: Zoho serves the CA DC from "zohocloud.ca".
REGION_DOMAINS: dict[str, str] = {
    "com": "com",
    "us": "com",
    "eu": "eu",
    "in": "in",
    "au": "com.au",
    "jp": "jp",
    "ca": "ca",  # handled specially below (zohocloud.ca)
}

SUPPORTED_REGIONS = sorted(set(REGION_DOMAINS.keys()))

API_VERSION_PATH = "/recruit/v2"


def _accounts_host(region: str) -> str:
    region = region.lower().strip()
    if region == "ca":
        return "https://accounts.zohocloud.ca"
    domain = REGION_DOMAINS.get(region, "com")
    return f"https://accounts.zoho.{domain}"


def _recruit_host(region: str) -> str:
    region = region.lower().strip()
    if region == "ca":
        return "https://recruit.zohocloud.ca"
    domain = REGION_DOMAINS.get(region, "com")
    return f"https://recruit.zoho.{domain}"


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Zoho OAuth credentials ---
    zoho_client_id: str = Field(default="", validation_alias="ZOHO_CLIENT_ID")
    zoho_client_secret: str = Field(default="", validation_alias="ZOHO_CLIENT_SECRET")
    zoho_refresh_token: str = Field(default="", validation_alias="ZOHO_REFRESH_TOKEN")

    # --- Zoho data center ---
    zoho_region: str = Field(default="com", validation_alias="ZOHO_REGION")

    # Optional explicit overrides. When unset they are derived from the region.
    zoho_base_url: Optional[str] = Field(default=None, validation_alias="ZOHO_BASE_URL")
    zoho_accounts_url: Optional[str] = Field(
        default=None, validation_alias="ZOHO_ACCOUNTS_URL"
    )

    # --- Transport / server ---
    mcp_transport: str = Field(default="stdio", validation_alias="MCP_TRANSPORT")
    http_host: str = Field(default="0.0.0.0", validation_alias="HTTP_HOST")
    http_port: int = Field(default=8000, validation_alias="HTTP_PORT")

    # --- Behaviour ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    request_timeout_seconds: float = Field(
        default=30.0, validation_alias="REQUEST_TIMEOUT_SECONDS"
    )
    max_retries: int = Field(default=3, validation_alias="MAX_RETRIES")
    rate_limit_per_minute: int = Field(
        default=100, validation_alias="RATE_LIMIT_PER_MINUTE"
    )

    @model_validator(mode="after")
    def _resolve_urls(self) -> "Settings":
        region = (self.zoho_region or "com").lower().strip()
        if region not in REGION_DOMAINS:
            raise ValueError(
                f"Unsupported ZOHO_REGION '{region}'. "
                f"Supported: {', '.join(SUPPORTED_REGIONS)}"
            )
        self.zoho_region = region
        if not self.zoho_accounts_url:
            self.zoho_accounts_url = _accounts_host(region)
        if not self.zoho_base_url:
            self.zoho_base_url = f"{_recruit_host(region)}{API_VERSION_PATH}"
        # Normalise: strip trailing slashes
        self.zoho_accounts_url = self.zoho_accounts_url.rstrip("/")
        self.zoho_base_url = self.zoho_base_url.rstrip("/")
        return self

    @property
    def token_endpoint(self) -> str:
        return f"{self.zoho_accounts_url}/oauth/v2/token"

    def has_credentials(self) -> bool:
        return all(
            [self.zoho_client_id, self.zoho_client_secret, self.zoho_refresh_token]
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
