"""Pydantic models for candidate inputs.

These validate/normalise tool inputs and map friendly field names onto the
Zoho Recruit Candidates module API names.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class CandidateCreate(BaseModel):
    first_name: Optional[str] = Field(default=None)
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None
    current_employer: Optional[str] = None
    resume_url: Optional[str] = None

    def to_zoho(self) -> dict:
        record: dict = {
            "Last_Name": self.last_name,
            "Email": self.email,
        }
        if self.first_name:
            record["First_Name"] = self.first_name
        if self.phone:
            record["Phone"] = self.phone
        if self.skills:
            record["Skill_Set"] = self.skills
        if self.experience_years is not None:
            record["Experience_in_Years"] = self.experience_years
        if self.current_employer:
            record["Current_Employer"] = self.current_employer
        if self.resume_url:
            record["Resume_URL"] = self.resume_url
        return record


class CandidateStatusUpdate(BaseModel):
    candidate_id: str
    status: str


class CandidateSearch(BaseModel):
    keyword: Optional[str] = None
    skills: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[float] = None
    status: Optional[str] = None
    job_id: Optional[str] = None
    page: int = 1
    per_page: int = 20
