"""Pydantic models for job opening inputs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    job_title: str
    department: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    hiring_manager: Optional[str] = None
    number_of_positions: Optional[int] = Field(default=None, ge=1)


class JobStatusUpdate(BaseModel):
    job_id: str
    status: str


class JobSearch(BaseModel):
    keyword: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    recruiter: Optional[str] = None
    page: int = 1
    per_page: int = 20
