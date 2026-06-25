"""Advanced AI-assist MCP tools: resume parsing, match scoring, summaries."""

from __future__ import annotations

from typing import Any, Optional, Union

from mcp.server.fastmcp import FastMCP

from ..services import Services
from ..utils.error_handler import tool_handler


def register(mcp: FastMCP, services: Services) -> None:
    @mcp.tool()
    @tool_handler("resume_parser")
    async def resume_parser(
        resume_base64: Optional[str] = None,
        resume_text: Optional[str] = None,
        use_zoho_parser: bool = False,
    ) -> dict[str, Any]:
        """Parse a resume into structured JSON (skills, experience, companies,
        education, projects). Provide a base64-encoded PDF or raw text."""
        return await services.ai.resume_parse(
            resume_base64=resume_base64,
            resume_text=resume_text,
            use_zoho_parser=use_zoho_parser,
        )

    @mcp.tool()
    @tool_handler("candidate_match_score")
    async def candidate_match_score(
        candidate_skills: Union[str, list[str]],
        job_description: str,
        candidate_summary: str = "",
    ) -> dict[str, Any]:
        """Score a candidate against a job description. Returns match_percentage,
        strengths, gaps, and a recommendation."""
        return services.ai.candidate_match(
            candidate_skills=candidate_skills,
            job_description=job_description,
            candidate_summary=candidate_summary,
        )

    @mcp.tool()
    @tool_handler("interview_summary_generator")
    async def interview_summary_generator(transcript: str) -> dict[str, Any]:
        """Turn an interview transcript into structured feedback: summary,
        strengths, concerns, and questions asked."""
        return services.ai.summarize_interview(transcript=transcript)
