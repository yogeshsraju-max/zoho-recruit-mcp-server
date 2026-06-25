"""Zoho Recruit MCP server entrypoint.

Builds a FastMCP server, registers every tool group, and runs it over the
configured transport:

  * STDIO            -> for Claude Desktop (default)
  * Streamable HTTP  -> for cloud / remote deployments and the MCP Inspector

Run:
    python -m src.server                 # stdio (Claude Desktop)
    MCP_TRANSPORT=http python -m src.server
    python -m src.server --transport http --port 8000

The HTTP transport also exposes an ASGI app via ``build_http_app()`` for use
with an external uvicorn/gunicorn process (see Dockerfile / docker-compose).
"""

from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .services import Services
from .tools import (
    ai_tools,
    analytics_tools,
    candidate_tools,
    email_tools,
    interview_tools,
    job_tools,
)
from .utils.logger import configure_logging, logger

SERVER_NAME = "zoho-recruit"


def build_server() -> tuple[FastMCP, Services]:
    """Construct the FastMCP server with all tools registered."""
    settings = get_settings()
    configure_logging(settings.log_level)

    mcp = FastMCP(
        SERVER_NAME,
        host=settings.http_host,
        port=settings.http_port,
    )
    services = Services(settings)

    candidate_tools.register(mcp, services)
    job_tools.register(mcp, services)
    interview_tools.register(mcp, services)
    analytics_tools.register(mcp, services)
    email_tools.register(mcp, services)
    ai_tools.register(mcp, services)

    if not settings.has_credentials():
        logger.bind(tool="startup").warning(
            "Zoho credentials are not fully configured; tool calls will fail "
            "until ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET / ZOHO_REFRESH_TOKEN are set."
        )
    logger.bind(tool="startup").info(
        "server '{}' ready (region={}, base_url={})",
        SERVER_NAME,
        settings.zoho_region,
        settings.zoho_base_url,
    )
    return mcp, services


def build_http_app():
    """Return a Streamable-HTTP ASGI app (for uvicorn `src.server:app`)."""
    mcp, _services = build_server()
    return mcp.streamable_http_app()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zoho Recruit MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport to run (default: stdio).",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.host:
        os.environ["HTTP_HOST"] = args.host
    if args.port:
        os.environ["HTTP_PORT"] = str(args.port)

    mcp, _services = build_server()

    if args.transport == "http":
        # Streamable HTTP exposes the MCP endpoint at /mcp.
        mcp.run(transport="streamable-http")
    elif args.transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


# Exposed for `uvicorn src.server:app`
app = None
if os.getenv("MCP_TRANSPORT", "").lower() == "http" and os.getenv("UVICORN_APP") == "1":
    app = build_http_app()


if __name__ == "__main__":
    main()
