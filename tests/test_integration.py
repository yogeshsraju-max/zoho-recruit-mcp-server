"""Integration tests exercising the full client + domain stack against a
mocked Zoho API (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.services import Services


def _token(settings):
    respx.post(settings.token_endpoint).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "expires_in": 3600}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_candidates_end_to_end(settings):
    _token(settings)
    respx.get(f"{settings.zoho_base_url}/Candidates/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "1", "First_Name": "Rahul", "Last_Name": "Sharma",
                     "Skill_Set": "Python, FastAPI"}
                ],
                "info": {"more_records": False},
            },
        )
    )
    services = Services(settings)
    result = await services.candidates.search(skills="Python")
    assert result["count"] == 1
    assert result["candidates"][0]["First_Name"] == "Rahul"
    await services.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_job_end_to_end(settings):
    _token(settings)
    respx.post(f"{settings.zoho_base_url}/Job_Openings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"status": "success", "details": {"id": "J-1"}}]},
        )
    )
    services = Services(settings)
    result = await services.jobs.create(
        job_title="Technical Program Manager", department="Engineering"
    )
    assert result["id"] == "J-1"
    await services.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_schedule_interview_end_to_end(settings):
    _token(settings)
    respx.post(f"{settings.zoho_base_url}/Interviews").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"status": "success", "details": {"id": "INT-9"}}]},
        )
    )
    services = Services(settings)
    result = await services.interviews.schedule(
        candidate_id="1",
        interviewer="alice@example.com",
        date="2026-07-01",
        time="14:30:00",
    )
    assert result["id"] == "INT-9"
    await services.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_hiring_funnel_end_to_end(settings):
    _token(settings)
    respx.get(f"{settings.zoho_base_url}/Candidates").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "1", "Candidate_Status": "Applied"},
                    {"id": "2", "Candidate_Status": "Interview"},
                    {"id": "3", "Candidate_Status": "Offer"},
                    {"id": "4", "Candidate_Status": "Joined"},
                ],
                "info": {"more_records": False},
            },
        )
    )
    services = Services(settings)
    report = await services.reports.hiring_funnel()
    assert report["total_applicants"] == 4
    assert report["stages"]["Joined"] == 1
    assert report["conversion"]["overall_join_pct"] == 25.0
    await services.aclose()
