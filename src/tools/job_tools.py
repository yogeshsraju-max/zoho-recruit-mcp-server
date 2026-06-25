"""Job management MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..models.job import JobCreate
from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("create_job_opening")
    async def create_job_opening(
        job_title: str,
        department: Optional[str] = None,
        experience: Optional[str] = None,
        skills: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        hiring_manager: Optional[str] = None,
        number_of_positions: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a new job opening in Zoho Recruit."""
        model = JobCreate(
            job_title=job_title,
            department=department,
            experience=experience,
            skills=skills,
            location=location,
            description=description,
            hiring_manager=hiring_manager,
            number_of_positions=number_of_positions,
        )
        return await services.jobs.create(
            job_title=model.job_title,
            department=model.department,
            experience=model.experience,
            skills=model.skills,
            location=model.location,
            description=model.description,
            hiring_manager=model.hiring_manager,
            number_of_positions=model.number_of_positions,
        )

    @mcp.tool()
    @tool_handler("search_jobs")
    async def search_jobs(
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        location: Optional[str] = None,
        recruiter: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Search job openings. Returns open positions, status, and the assigned
        recruiter. Use get_job_pipeline for the candidate pipeline of a job."""
        return await services.jobs.search(
            keyword=keyword,
            status=status,
            department=department,
            location=location,
            recruiter=recruiter,
            page=page,
            per_page=per_page,
        )

    @mcp.tool()
    @tool_handler("get_job_pipeline")
    async def get_job_pipeline(job_id: str) -> dict[str, Any]:
        """List the candidates currently associated with a job opening."""
        return await services.jobs.get_pipeline(job_id)

    @mcp.tool()
    @tool_handler("update_job_status")
    async def update_job_status(job_id: str, status: str) -> dict[str, Any]:
        """Update a job opening's status (e.g. Open, Hold, Closed)."""
        return await services.jobs.update_status(job_id, status)

    @mcp.tool()
    @tool_handler("move_candidate_in_pipeline")
    async def move_candidate_in_pipeline(
        job_id: str,
        candidate_id: str,
        status: str,
        comments: Optional[str] = None,
    ) -> dict[str, Any]:
        """Move a candidate to a new stage within a specific job's pipeline,
        e.g. "Move candidate to Technical Interview stage"."""
        return await services.jobs.change_candidate_stage(
            job_id, candidate_id, status, comments
        )
