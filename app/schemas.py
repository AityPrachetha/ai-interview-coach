"""
Pydantic schemas — request/response shapes for the API.
Kept separate from SQLAlchemy models so the DB layer can change
without breaking the API contract.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import InterviewType, InterviewStatus


# ---------- Auth ----------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Resume ----------

class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: Optional[str]
    extracted_skills: Optional[dict] = None
    created_at: datetime


# ---------- Job Description ----------

class JobDescriptionCreate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    raw_text: str


class JobDescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: Optional[str]
    company: Optional[str]
    extracted_requirements: Optional[dict] = None
    created_at: datetime


# ---------- Interview Session ----------

class InterviewSessionCreate(BaseModel):
    resume_id: str
    job_description_id: str
    interview_type: InterviewType


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    text: str
    order_index: int
    topic: Optional[str]
    is_followup: int


class InterviewSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    interview_type: InterviewType
    status: InterviewStatus
    resume_match_score: Optional[float] = None
    skill_match_details: Optional[dict] = None
    questions: List[QuestionOut] = []
    created_at: datetime
