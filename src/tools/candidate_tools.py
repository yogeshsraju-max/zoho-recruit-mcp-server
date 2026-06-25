"""Candidate management MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..models.candidate import CandidateCreate
from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("search_candidates")
    async def search_candidates(
        keyword: Optional[str] = None,
        skills: Optional[str] = None,
        location: Optional[str] = None,
        experience: Optional[float] = None,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Search candidates in Zoho Recruit.

        Filter by free-text keyword, comma-separated skills, location, minimum
        years of experience, candidate status, or an associated job id.
        Example: "Find Python developers with 5+ years experience".
        """
        return await services.candidates.search(
            keyword=keyword,
            skills=skills,
            location=location,
            experience=experience,
            status=status,
            job_id=job_id,
            page=page,
            per_page=per_page,
        )

    @mcp.tool()
    @tool_handler("get_candidate_details")
    async def get_candidate_details(candidate_id: str) -> dict[str, Any]:
        """Get a candidate's full profile: contact info, experience, skills,
        current company, status, and interview history."""
        return await services.candidates.get_details(candidate_id)

    @mcp.tool()
    @tool_handler("create_candidate")
    async def create_candidate(
        last_name: str,
        email: str,
        first_name: Optional[str] = None,
        phone: Optional[str] = None,
        skills: Optional[str] = None,
        experience_years: Optional[float] = None,
        current_employer: Optional[str] = None,
        resume_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new candidate profile in Zoho Recruit."""
        model = CandidateCreate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            skills=skills,
            experience_years=experience_years,
            current_employer=current_employer,
            resume_url=resume_url,
        )
        return await services.candidates.create(model.to_zoho())

    @mcp.tool()
    @tool_handler("update_candidate_status")
    async def update_candidate_status(candidate_id: str, status: str) -> dict[str, Any]:
        """Move a candidate to a new stage (e.g. Applied, Screening, Assessment,
        Interview, Offer, Joined, Rejected)."""
        return await services.candidates.update_status(candidate_id, status)

    @mcp.tool()
    @tool_handler("bulk_candidate_update")
    async def bulk_candidate_update(updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update many candidates at once. Each item must include an 'id' plus
        the fields to change, e.g. [{"id":"123","Candidate_Status":"Rejected"}].
        Useful for "reject all candidates who failed assessment"."""
        return await services.candidates.bulk_update(updates)
