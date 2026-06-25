"""Interview operations against the Zoho Recruit Interviews module."""

from __future__ import annotations

from typing import Any

from ..utils.error_handler import InvalidInputError
from .client import ZohoClient
from .common import (
    MODULE_INTERVIEWS,
    and_,
    criterion,
    first_record,
    page_info,
    records_from,
)


class InterviewsAPI:
    def __init__(self, client: ZohoClient):
        self._client = client

    async def schedule(
        self,
        *,
        candidate_id: str,
        interviewer: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        meeting_link: str | None = None,
        interview_name: str | None = None,
    ) -> dict[str, Any]:
        if not all([candidate_id, interviewer, date, time]):
            raise InvalidInputError(
                "candidate_id, interviewer, date and time are required"
            )
        # Zoho stores schedule as datetime strings. We compose an ISO-8601
        # start; "From"/"To" field API names may vary by account template.
        start = f"{date}T{time}"
        record: dict[str, Any] = {
            "Interview_Name": interview_name or "Interview",
            "Candidate_Name": candidate_id,  # lookup by id
            "Interviewer": interviewer,
            "Start_DateTime": start,
            "Duration": duration_minutes,
        }
        if meeting_link:
            record["Meeting_Link"] = meeting_link
        resp = await self._client.post(
            f"/{MODULE_INTERVIEWS}", json={"data": [record]}
        )
        return self._mutation_result(resp)

    async def get_schedule(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        interviewer: str | None = None,
        pending_feedback_only: bool = False,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        if from_date:
            clauses.append(criterion("Start_DateTime", "greater_equal", from_date))
        if to_date:
            clauses.append(criterion("Start_DateTime", "less_equal", to_date))
        if interviewer:
            clauses.append(criterion("Interviewer", "equals", interviewer))
        if pending_feedback_only:
            clauses.append(criterion("Interview_Status", "equals", "Scheduled"))

        params: dict[str, Any] = {"page": page, "per_page": per_page}
        criteria = and_(*clauses)
        if criteria:
            params["criteria"] = criteria
            resp = await self._client.get(
                f"/{MODULE_INTERVIEWS}/search", params=params
            )
        else:
            resp = await self._client.get(f"/{MODULE_INTERVIEWS}", params=params)

        return {
            "interviews": records_from(resp),
            "info": page_info(resp),
            "count": len(records_from(resp)),
        }

    async def submit_feedback(
        self,
        *,
        candidate_id: str,
        interviewer: str,
        rating: float | int,
        feedback: str,
        recommendation: str,
        interview_id: str | None = None,
    ) -> dict[str, Any]:
        if not candidate_id or feedback is None:
            raise InvalidInputError("candidate_id and feedback are required")
        record: dict[str, Any] = {
            "Candidate_Name": candidate_id,
            "Interviewer": interviewer,
            "Rating": rating,
            "Feedback": feedback,
            "Recommendation": recommendation,
            "Interview_Status": "Completed",
        }
        if interview_id:
            # Update an existing interview record's feedback.
            resp = await self._client.put(
                f"/{MODULE_INTERVIEWS}/{interview_id}",
                json={"data": [record]},
            )
        else:
            resp = await self._client.post(
                f"/{MODULE_INTERVIEWS}", json={"data": [record]}
            )
        return self._mutation_result(resp)

    @staticmethod
    def _mutation_result(resp: dict[str, Any]) -> dict[str, Any]:
        record = first_record(resp) or {}
        details = record.get("details", {}) if isinstance(record, dict) else {}
        return {
            "status": record.get("status", "success"),
            "id": details.get("id"),
            "raw": record,
        }
