"""HelixDB API schemas (Pydantic)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- Auth / Users
class LoginRequest(BaseModel):
    staff_id: str
    password: str = "helixdb"


class UserOut(BaseModel):
    id: int
    staff_id: str
    name: str
    role: str
    designation: str = ""
    department: str = ""
    specialisation: str = ""
    email: str = ""
    created_at: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    specialisation: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class UserCreate(BaseModel):
    staff_id: str
    name: str
    role: str = "faculty"
    designation: str = ""
    department: str = ""
    specialisation: str = ""
    email: str = ""
    password: str = "helixdb"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- Research
class Author(BaseModel):
    staff_id: str = ""
    name: str = ""
    corresponding: bool = False
    role: str = ""  # principal_author | co_author | supervisor | ...
    order: int = 1


class ProjectIn(BaseModel):
    staff_id: Optional[str] = None  # defaults to current user
    category: str = "paper"
    type: str = "journal"
    title: str = Field(..., min_length=2)
    status: str = "Active"
    year: Optional[int] = None
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    authors: list[Author] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    doi: str = ""
    isbn: str = ""
    patent_no: str = ""
    funding_agency: str = ""
    verification_status: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    staff_id: str
    category: str
    type: str
    title: str
    status: str
    year: Optional[int]
    description: str
    details: dict[str, Any] = {}
    authors: list[Any] = []
    metadata: dict[str, Any] = {}
    verification_status: str
    score: float = 0
    score_breakdown: dict[str, Any] = {}
    doi: str = ""
    isbn: str = ""
    patent_no: str = ""
    funding_agency: str = ""
    source: str = "manual"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    likes: int = 0
    comments: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------- Events
class EventIn(BaseModel):
    title: str = Field(..., min_length=2)
    date: str
    type: str = "Seminar"
    description: str = ""


# ---------------------------------------------------------------- Social
class CommentIn(BaseModel):
    text: str = Field(..., min_length=1)


# ---------------------------------------------------------------- Workload
class WorkloadEntry(BaseModel):
    month: str
    total_hours: int = 0
    teaching: int = 0
    research: int = 0
    administration: int = 0


# ---------------------------------------------------------------- Settings
class CollegeConfig(BaseModel):
    name: str
    logo: str = ""
    email: str = ""
    address: str = ""
    phone: str = ""
    research_cell: str = ""
    tagline: str = ""


class DatabaseConfig(BaseModel):
    enabled: bool = False
    apiBaseUrl: str = "/api"
    dbName: str = "researchmitra"


class BackupConfig(BaseModel):
    enabled: bool = True
    scheduled: bool = False
    interval_days: int = 7
    retention: int = 10
    last_backup: Optional[str] = None
    path: str = ""


class VerificationDecision(BaseModel):
    action: str  # approve | reject | request_changes | freeze | unfreeze
    comment: str = ""
