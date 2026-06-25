"""Job opening operations against the Zoho Recruit Job_Openings module."""

from __future__ import annotations

from typing import Any, Sequence

from ..utils.error_handler import InvalidInputError, NotFoundError
from .client import ZohoClient
from .common import (
    MODULE_JOBS,
    and_,
    criterion,
    first_record,
    join_skills,
    page_info,
    records_from,
)

JOB_DETAIL_FIELDS = [
    "id",
    "Posting_Title",
    "Department_Name",
    "Work_Experience",
    "Required_Skills",
    "City",
    "Job_Description",
    "Assigned_Recruiter",
    "Job_Opening_Status",
    "Number_of_Positions",
    "Created_Time",
]


class JobsAPI:
    def __init__(self, client: ZohoClient):
        self._client = client

    async def create(
        self,
        *,
        job_title: str,
        department: str | None = None,
        experience: str | None = None,
        skills: Sequence[str] | str | None = None,
        location: str | None = None,
        description: str | None = None,
        hiring_manager: str | None = None,
        number_of_positions: int | None = None,
    ) -> dict[str, Any]:
        if not job_title:
            raise InvalidInputError("job_title is required")
        record: dict[str, Any] = {"Posting_Title": job_title}
        if department:
            record["Department_Name"] = department
        if experience:
            record["Work_Experience"] = experience
        skill_value = join_skills(skills)
        if skill_value:
            record["Required_Skills"] = skill_value
        if location:
            record["City"] = location
        if description:
            record["Job_Description"] = description
        if hiring_manager:
            # Zoho exposes hiring manager as a user lookup; many orgs use a
            # custom field. Confirm the API name for your account.
            record["Hiring_Manager"] = hiring_manager
        if number_of_positions:
            record["Number_of_Positions"] = number_of_positions

        resp = await self._client.post(f"/{MODULE_JOBS}", json={"data": [record]})
        return self._mutation_result(resp)

    async def search(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        department: str | None = None,
        location: str | None = None,
        recruiter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        if status:
            clauses.append(criterion("Job_Opening_Status", "equals", status))
        if department:
            clauses.append(criterion("Department_Name", "equals", department))
        if location:
            clauses.append(criterion("City", "equals", location))
        if recruiter:
            clauses.append(criterion("Assigned_Recruiter", "equals", recruiter))

        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "fields": ",".join(JOB_DETAIL_FIELDS),
        }
        criteria = and_(*clauses)
        if criteria:
            params["criteria"] = criteria
            resp = await self._client.get(f"/{MODULE_JOBS}/search", params=params)
        elif keyword:
            params["word"] = keyword
            resp = await self._client.get(f"/{MODULE_JOBS}/search", params=params)
        else:
            resp = await self._client.get(f"/{MODULE_JOBS}", params=params)

        return {
            "jobs": records_from(resp),
            "info": page_info(resp),
            "count": len(records_from(resp)),
        }

    async def update_status(self, job_id: str, status: str) -> dict[str, Any]:
        if not job_id or not status:
            raise InvalidInputError("job_id and status are required")
        resp = await self._client.put(
            f"/{MODULE_JOBS}/{job_id}",
            json={"data": [{"Job_Opening_Status": status}]},
        )
        return self._mutation_result(resp)

    async def get_pipeline(self, job_id: str) -> dict[str, Any]:
        """Return candidates associated with a job opening.

        Zoho exposes associated candidates via the "associate" relationship.
        ENDPOINT (confirm for your account):
            GET /Job_Openings/{job_id}/associate
        Some accounts use ../Candidates as the related list name instead.
        """
        if not job_id:
            raise InvalidInputError("job_id is required")
        try:
            resp = await self._client.get(f"/{MODULE_JOBS}/{job_id}/associate")
        except NotFoundError:
            # Fallback: try the related-records endpoint name.
            resp = await self._client.get(f"/{MODULE_JOBS}/{job_id}/Candidates")
        return {"job_id": job_id, "candidates": records_from(resp)}

    async def change_candidate_stage(
        self, job_id: str, candidate_id: str, status: str, comments: str | None = None
    ) -> dict[str, Any]:
        """Move a candidate to a new stage within a job's pipeline.

        ENDPOINT (confirm for your account): Zoho Recruit's change-status action
        associates a candidate to a job opening with a target status:
            PUT /Job_Openings/{job_id}/associate
            body: {"data": [{"ids": ["<candidate_id>"],
                              "Candidate_Status": "<status>",
                              "comments": "<optional>"}]}
        """
        if not all([job_id, candidate_id, status]):
            raise InvalidInputError("job_id, candidate_id and status are required")
        item: dict[str, Any] = {
            "ids": [candidate_id],
            "Candidate_Status": status,
        }
        if comments:
            item["comments"] = comments
        resp = await self._client.put(
            f"/{MODULE_JOBS}/{job_id}/associate", json={"data": [item]}
        )
        return {"job_id": job_id, "candidate_id": candidate_id, "status": status, "raw": resp}

    @staticmethod
    def _mutation_result(resp: dict[str, Any]) -> dict[str, Any]:
        record = first_record(resp) or {}
        details = record.get("details", {}) if isinstance(record, dict) else {}
        return {
            "status": record.get("status", "success"),
            "id": details.get("id"),
            "raw": record,
        }
