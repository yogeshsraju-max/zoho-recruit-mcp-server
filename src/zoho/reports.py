"""Recruitment analytics built on top of the Candidates / Interviews modules.

These aggregate by paging through records and tallying locally. For very large
data sets, prefer Zoho's COQL endpoint (POST /coql) with GROUP BY; a COQL helper
is provided and marked for configuration.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .client import ZohoClient
from .common import MODULE_CANDIDATES, and_, criterion, records_from

# Canonical stage buckets used for the funnel. Map your org's status picklist
# values onto these buckets if they differ.
FUNNEL_STAGES = [
    "Applied",
    "Screening",
    "Assessment",
    "Interview",
    "Offer",
    "Joined",
    "Rejected",
]

# Optional alias map: org-specific status -> canonical bucket.
STAGE_ALIASES = {
    "New": "Applied",
    "Submitted": "Applied",
    "Phone Screen": "Screening",
    "Test": "Assessment",
    "Technical Interview": "Interview",
    "Hired": "Joined",
    "Declined": "Rejected",
}

_MAX_PAGES = 20  # safety cap (20 * per_page records)


class ReportsAPI:
    def __init__(self, client: ZohoClient):
        self._client = client

    async def _fetch_candidates(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        role: str | None = None,
        recruiter: str | None = None,
        department: str | None = None,
        per_page: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        if date_from:
            clauses.append(criterion("Created_Time", "greater_equal", date_from))
        if date_to:
            clauses.append(criterion("Created_Time", "less_equal", date_to))
        if role:
            clauses.append(criterion("Job_Opening_Name", "equals", role))
        if recruiter:
            clauses.append(criterion("Source", "equals", recruiter))
        if department:
            clauses.append(criterion("Department", "equals", department))

        criteria = and_(*clauses)
        records: list[dict[str, Any]] = []
        page = 1
        while page <= _MAX_PAGES:
            params: dict[str, Any] = {"page": page, "per_page": per_page}
            if criteria:
                params["criteria"] = criteria
                resp = await self._client.get(
                    f"/{MODULE_CANDIDATES}/search", params=params
                )
            else:
                resp = await self._client.get(f"/{MODULE_CANDIDATES}", params=params)
            batch = records_from(resp)
            records.extend(batch)
            more = bool(resp.get("info", {}).get("more_records"))
            if not batch or not more:
                break
            page += 1
        return records

    @staticmethod
    def _bucket(status: str | None) -> str | None:
        if not status:
            return None
        if status in FUNNEL_STAGES:
            return status
        return STAGE_ALIASES.get(status)

    async def hiring_funnel(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        role: str | None = None,
        recruiter: str | None = None,
        department: str | None = None,
    ) -> dict[str, Any]:
        records = await self._fetch_candidates(
            date_from=date_from,
            date_to=date_to,
            role=role,
            recruiter=recruiter,
            department=department,
        )
        counts: Counter[str] = Counter()
        for r in records:
            bucket = self._bucket(r.get("Candidate_Status"))
            if bucket:
                counts[bucket] += 1

        total = len(records)
        offers = counts.get("Offer", 0)
        joiners = counts.get("Joined", 0)
        interviews = counts.get("Interview", 0)

        def pct(n: int, d: int) -> float:
            return round((n / d) * 100, 2) if d else 0.0

        return {
            "total_applicants": total,
            "stages": {stage: counts.get(stage, 0) for stage in FUNNEL_STAGES},
            "conversion": {
                "applicant_to_interview_pct": pct(interviews, total),
                "interview_to_offer_pct": pct(offers, interviews),
                "offer_to_join_pct": pct(joiners, offers),
                "overall_join_pct": pct(joiners, total),
            },
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "role": role,
                "recruiter": recruiter,
                "department": department,
            },
        }

    async def recruiter_performance(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> dict[str, Any]:
        records = await self._fetch_candidates(date_from=date_from, date_to=date_to)
        by_recruiter: dict[str, dict[str, int]] = {}
        for r in records:
            owner = r.get("Source") or r.get("Owner", {}).get("name") if isinstance(
                r.get("Owner"), dict
            ) else r.get("Source") or "Unknown"
            owner = owner or "Unknown"
            stats = by_recruiter.setdefault(
                owner, {"sourced": 0, "interviews": 0, "offers": 0, "closures": 0}
            )
            stats["sourced"] += 1
            bucket = self._bucket(r.get("Candidate_Status"))
            if bucket == "Interview":
                stats["interviews"] += 1
            elif bucket == "Offer":
                stats["offers"] += 1
            elif bucket == "Joined":
                stats["closures"] += 1
        return {"recruiters": by_recruiter, "filters": {"date_from": date_from, "date_to": date_to}}

    async def source_analysis(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> dict[str, Any]:
        records = await self._fetch_candidates(date_from=date_from, date_to=date_to)
        counts: Counter[str] = Counter()
        joined: Counter[str] = Counter()
        for r in records:
            source = r.get("Source") or "Unknown"
            counts[source] += 1
            if self._bucket(r.get("Candidate_Status")) == "Joined":
                joined[source] += 1
        return {
            "sources": {
                src: {
                    "candidates": counts[src],
                    "joined": joined.get(src, 0),
                    "join_rate_pct": round((joined.get(src, 0) / counts[src]) * 100, 2)
                    if counts[src]
                    else 0.0,
                }
                for src in counts
            },
            "filters": {"date_from": date_from, "date_to": date_to},
        }

    async def coql(self, query: str) -> dict[str, Any]:
        """Run a raw COQL query (advanced aggregation).

        ENDPOINT: POST /coql  with body {"select_query": "<sql-like>"}.
        Useful for GROUP BY counts on large datasets.
        """
        return await self._client.post("/coql", json={"select_query": query})
