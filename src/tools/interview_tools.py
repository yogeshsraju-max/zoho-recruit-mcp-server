"""Interview management MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("schedule_interview")
    async def schedule_interview(
        candidate_id: str,
        interviewer: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        meeting_link: Optional[str] = None,
        interview_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Schedule an interview. ``date`` is YYYY-MM-DD and ``time`` is HH:MM
        (24h, with optional timezone offset, e.g. 14:30:00+05:30)."""
        return await services.interviews.schedule(
            candidate_id=candidate_id,
            interviewer=interviewer,
            date=date,
            time=time,
            duration_minutes=duration_minutes,
            meeting_link=meeting_link,
            interview_name=interview_name,
        )

    @mcp.tool()
    @tool_handler("get_interview_schedule")
    async def get_interview_schedule(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        interviewer: Optional[str] = None,
        pending_feedback_only: bool = False,
    ) -> dict[str, Any]:
        """List upcoming interviews and pending evaluations. Set
        ``pending_feedback_only=true`` to show interviews awaiting feedback."""
        return await services.interviews.get_schedule(
            from_date=from_date,
            to_date=to_date,
            interviewer=interviewer,
            pending_feedback_only=pending_feedback_only,
        )

    @mcp.tool()
    @tool_handler("submit_interview_feedback")
    async def submit_interview_feedback(
        candidate_id: str,
        interviewer: str,
        rating: float,
        feedback: str,
        recommendation: str,
        interview_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit interview feedback. ``recommendation`` is typically one of
        Hire / No Hire / Hold. Pass ``interview_id`` to update an existing
        interview record instead of creating one."""
        return await services.interviews.submit_feedback(
            candidate_id=candidate_id,
            interviewer=interviewer,
            rating=rating,
            feedback=feedback,
            recommendation=recommendation,
            interview_id=interview_id,
        )
