"""Unit tests for domain APIs and AI helpers using the stub client."""

from __future__ import annotations

import pytest

from src.utils.error_handler import InvalidInputError
from src.zoho.ai_helpers import AIHelpers
from src.zoho.candidates import CandidatesAPI
from src.zoho.jobs import JobsAPI


@pytest.mark.asyncio
async def test_candidate_search_builds_criteria(stub_client):
    stub_client.queue("GET /Candidates/search", {"data": [{"id": "1"}], "info": {}})
    api = CandidatesAPI(stub_client)
    result = await api.search(skills="Python", experience=5, location="Pune")
    assert result["count"] == 1
    _, path, params, _ = stub_client.calls[0]
    assert path == "/Candidates/search"
    crit = params["criteria"]
    assert "Skill_Set:starts_with:Python" in crit
    assert "Experience_in_Years:greater_equal:5" in crit
    assert "City:equals:Pune" in crit


@pytest.mark.asyncio
async def test_candidate_create_requires_email(stub_client):
    api = CandidatesAPI(stub_client)
    with pytest.raises(InvalidInputError):
        await api.create({"Last_Name": "Sharma"})  # missing Email


@pytest.mark.asyncio
async def test_candidate_create_returns_id(stub_client):
    stub_client.queue(
        "POST /Candidates",
        {"data": [{"status": "success", "details": {"id": "555"}}]},
    )
    api = CandidatesAPI(stub_client)
    result = await api.create({"Last_Name": "Sharma", "Email": "r@example.com"})
    assert result["id"] == "555"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_bulk_update_requires_ids(stub_client):
    api = CandidatesAPI(stub_client)
    with pytest.raises(InvalidInputError):
        await api.bulk_update([{"Candidate_Status": "Rejected"}])


@pytest.mark.asyncio
async def test_job_create_requires_title(stub_client):
    api = JobsAPI(stub_client)
    with pytest.raises(InvalidInputError):
        await api.create(job_title="")


@pytest.mark.asyncio
async def test_job_status_update(stub_client):
    stub_client.queue(
        "PUT /Job_Openings/77",
        {"data": [{"status": "success", "details": {"id": "77"}}]},
    )
    api = JobsAPI(stub_client)
    result = await api.update_status("77", "Closed")
    assert result["id"] == "77"


def test_candidate_match_score():
    ai = AIHelpers()
    result = ai.candidate_match(
        candidate_skills=["Python", "FastAPI", "AWS"],
        job_description="Looking for a Python engineer with FastAPI and Docker.",
    )
    assert 0 <= result["match_percentage"] <= 100
    assert "python" in result["strengths"]
    assert "docker" in result["gaps"]


def test_interview_summary_structuring():
    ai = AIHelpers()
    transcript = (
        "The candidate had strong system design skills. "
        "However, the SQL answers were weak. "
        "Did you work with Kafka before?"
    )
    result = ai.summarize_interview(transcript=transcript)
    assert result["strengths"]
    assert result["concerns"]
    assert result["questions_asked"]


async def test_resume_text_heuristics():
    ai = AIHelpers()

    text = (
        "John Doe\nEmail: john@example.com\n"
        "Skills: Python, React.js, Docker\n"
        "Experience\n8 years building web apps at Acme\n"
        "Education\nB.Tech Computer Science"
    )
    result = await ai.resume_parse(resume_text=text)
    parsed = result["parsed"]
    assert "python" in parsed["skills"]
    assert parsed["experience_years"] == 8
