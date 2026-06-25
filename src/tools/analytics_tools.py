"""Recruitment analytics MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("hiring_funnel_report")
    async def hiring_funnel_report(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        role: Optional[str] = None,
        recruiter: Optional[str] = None,
        department: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate a hiring funnel: applicants, screening, interview, offers,
        joiners, rejections, and conversion percentages. Dates are YYYY-MM-DD."""
        return await services.reports.hiring_funnel(
            date_from=date_from,
            date_to=date_to,
            role=role,
            recruiter=recruiter,
            department=department,
        )

    @mcp.tool()
    @tool_handler("recruiter_performance_report")
    async def recruiter_performance_report(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Per-recruiter metrics: candidates sourced, interviews, offers,
        closures."""
        return await services.reports.recruiter_performance(
            date_from=date_from, date_to=date_to
        )

    @mcp.tool()
    @tool_handler("source_analysis")
    async def source_analysis(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyse candidate sources (LinkedIn, Naukri, Referral, Careers page)
        with per-source counts and join rates."""
        return await services.reports.source_analysis(
            date_from=date_from, date_to=date_to
        )
