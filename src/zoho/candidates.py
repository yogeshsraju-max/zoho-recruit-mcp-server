"""Candidate operations against the Zoho Recruit Candidates module."""

from __future__ import annotations

from typing import Any, Sequence

from ..utils.error_handler import InvalidInputError, NotFoundError
from .client import ZohoClient
from .common import (
    MODULE_CANDIDATES,
    and_,
    criterion,
    first_record,
    join_skills,
    page_info,
    records_from,
)

# Default fields requested for candidate detail views.
CANDIDATE_DETAIL_FIELDS = [
    "id",
    "First_Name",
    "Last_Name",
    "Email",
    "Phone",
    "Mobile",
    "Experience_in_Years",
    "Skill_Set",
    "Current_Employer",
    "Current_Job_Title",
    "City",
    "Candidate_Status",
    "Source",
    "Created_Time",
]


class CandidatesAPI:
    def __init__(self, client: ZohoClient):
        self._client = client

    async def search(
        self,
        *,
        keyword: str | None = None,
        skills: Sequence[str] | str | None = None,
        location: str | None = None,
        experience: float | int | None = None,
        status: str | None = None,
        job_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Search candidates.

        ``experience`` is treated as a minimum (>=) number of years.
        ``keyword`` falls back to Zoho's free-text ``word`` search when no
        structured criteria are supplied.
        """
        clauses: list[str] = []
        if skills:
            skill_value = join_skills(skills)
            if skill_value:
                clauses.append(criterion("Skill_Set", "starts_with", skill_value))
        if location:
            clauses.append(criterion("City", "equals", location))
        if experience is not None:
            clauses.append(criterion("Experience_in_Years", "greater_equal", experience))
        if status:
            clauses.append(criterion("Candidate_Status", "equals", status))

        params: dict[str, Any] = {"page": page, "per_page": per_page}

        if job_id:
            # Candidates associated with a specific job opening.
            # Endpoint: GET /Job_Openings/{id}/associate  (see jobs module).
            # Here we filter by criteria when the module exposes a job lookup.
            clauses.append(criterion("Job_Opening_Name", "equals", job_id))

        criteria = and_(*clauses)
        if criteria:
            params["criteria"] = criteria
            resp = await self._client.get(f"/{MODULE_CANDIDATES}/search", params=params)
        elif keyword:
            params["word"] = keyword
            resp = await self._client.get(f"/{MODULE_CANDIDATES}/search", params=params)
        else:
            # No filters: return a recent page of candidates.
            resp = await self._client.get(f"/{MODULE_CANDIDATES}", params=params)

        records = records_from(resp)
        if keyword and criteria:
            # Post-filter structured results by keyword for relevance.
            kw = keyword.lower()
            records = [
                r
                for r in records
                if kw in (str(r.get("Skill_Set", "")) + " " +
                          str(r.get("Current_Job_Title", "")) + " " +
                          str(r.get("First_Name", "")) + " " +
                          str(r.get("Last_Name", ""))).lower()
            ]
        return {"candidates": records, "info": page_info(resp), "count": len(records)}

    async def get_details(self, candidate_id: str) -> dict[str, Any]:
        if not candidate_id:
            raise InvalidInputError("candidate_id is required")
        resp = await self._client.get(
            f"/{MODULE_CANDIDATES}/{candidate_id}",
            params={"fields": ",".join(CANDIDATE_DETAIL_FIELDS)},
        )
        record = first_record(resp)
        if not record:
            raise NotFoundError(f"No candidate with id {candidate_id}")
        # Best-effort enrichment with interview history (non-fatal).
        record["interview_history"] = await self._safe_interview_history(candidate_id)
        return record

    async def _safe_interview_history(self, candidate_id: str) -> list[dict[str, Any]]:
        try:
            from .common import MODULE_INTERVIEWS

            resp = await self._client.get(
                f"/{MODULE_INTERVIEWS}/search",
                params={"criteria": criterion("Candidate_Name", "equals", candidate_id)},
            )
            return records_from(resp)
        except Exception:  # noqa: BLE001 - enrichment must never break details
            return []

    async def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        required = ["Last_Name", "Email"]
        missing = [f for f in required if not fields.get(f)]
        if missing:
            raise InvalidInputError(
                f"Missing required candidate fields: {', '.join(missing)}"
            )
        resp = await self._client.post(
            f"/{MODULE_CANDIDATES}", json={"data": [fields]}
        )
        return self._mutation_result(resp)

    async def update_status(self, candidate_id: str, status: str) -> dict[str, Any]:
        if not candidate_id or not status:
            raise InvalidInputError("candidate_id and status are required")
        # NOTE: This updates the Candidate_Status field directly. Moving a
        # candidate through a *job-specific* pipeline may instead require the
        # "change status" associate endpoint:
        #   PUT /Job_Openings/{job_id}/associate  with status payload.
        # That variant is exposed via jobs.JobsAPI.change_candidate_stage().
        resp = await self._client.put(
            f"/{MODULE_CANDIDATES}/{candidate_id}",
            json={"data": [{"Candidate_Status": status}]},
        )
        return self._mutation_result(resp)

    async def bulk_update(
        self, updates: Sequence[dict[str, Any]]
    ) -> dict[str, Any]:
        """Update many candidates. Each item must contain an ``id`` key.

        Zoho's mass-update endpoint accepts up to 100 records per call.
        """
        if not updates:
            raise InvalidInputError("updates list is empty")
        for u in updates:
            if not u.get("id"):
                raise InvalidInputError("every update item must include an 'id'")
        results: list[dict[str, Any]] = []
        for batch_start in range(0, len(updates), 100):
            batch = list(updates[batch_start : batch_start + 100])
            resp = await self._client.put(
                f"/{MODULE_CANDIDATES}", json={"data": batch}
            )
            results.extend(records_from(resp) or [resp])
        return {"updated": len(updates), "results": results}

    @staticmethod
    def _mutation_result(resp: dict[str, Any]) -> dict[str, Any]:
        record = first_record(resp) or {}
        details = record.get("details", {}) if isinstance(record, dict) else {}
        return {
            "status": record.get("status", "success"),
            "id": details.get("id"),
            "raw": record,
        }
