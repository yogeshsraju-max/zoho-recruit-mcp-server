"""Email automation MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("send_candidate_email")
    async def send_candidate_email(
        candidate_id: str,
        template: Optional[str] = None,
        message: Optional[str] = None,
        subject: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an email to a candidate. ``template`` is one of rejection,
        interview_invitation, follow_up, offer (used to derive a subject), or
        pass a Zoho ``template_id`` for a branded template. Provide ``message``
        for an ad-hoc body."""
        return await services.email.send(
            candidate_id=candidate_id,
            template=template,
            message=message,
            subject=subject,
            template_id=template_id,
        )
