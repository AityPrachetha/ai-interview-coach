"""
Core DB schema.

Covers Phase 1 (users, resumes, job descriptions, skill match) and
lays the tables needed by later phases (interview sessions, questions,
answers, scores) so we don't have to redo migrations soon.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Float, Integer, Enum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class InterviewType(str, enum.Enum):
    HR = "HR"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"


class InterviewStatus(str, enum.Enum):
    CREATED = "CREATED"           # session created, questions not generated yet
    QUESTIONS_READY = "QUESTIONS_READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    resumes = relationship("Resume", back_populates="owner", cascade="all, delete-orphan")
    job_descriptions = relationship("JobDescription", back_populates="owner", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="owner", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)

    original_filename = Column(String(500))
    storage_path = Column(String(1000))          # where the raw file lives on disk/S3
    raw_text = Column(Text)                       # extracted plain text
    extracted_skills = Column(JSON, nullable=True)  # {"skills": [...], "years_experience": {...}, ...}

    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="resumes")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)

    title = Column(String(500), nullable=True)
    company = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=False)
    extracted_requirements = Column(JSON, nullable=True)  # {"required_skills": [...], "nice_to_have": [...]}

    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="job_descriptions")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    resume_id = Column(UUID(as_uuid=False), ForeignKey("resumes.id"), nullable=False)
    job_description_id = Column(UUID(as_uuid=False), ForeignKey("job_descriptions.id"), nullable=False)

    interview_type = Column(Enum(InterviewType), nullable=False)
    status = Column(Enum(InterviewStatus), default=InterviewStatus.CREATED)

    resume_match_score = Column(Float, nullable=True)   # 0-100, computed in Phase 1
    skill_match_details = Column(JSON, nullable=True)   # matched / missing skills breakdown

    # Final report fields (populated in later phases)
    confidence_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    behavioral_score = Column(Float, nullable=True)
    hiring_readiness_score = Column(Float, nullable=True)
    improvement_suggestions = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="interview_sessions")
    questions = relationship("Question", back_populates="session", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("interview_sessions.id"), nullable=False)

    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)
    topic = Column(String(255), nullable=True)          # e.g. "Python", "Leadership", "STAR - Conflict"
    is_followup = Column(Integer, default=0)             # 0 = primary question, 1 = follow-up
    parent_question_id = Column(UUID(as_uuid=False), ForeignKey("questions.id"), nullable=True)

    session = relationship("InterviewSession", back_populates="questions")
    answer = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    question_id = Column(UUID(as_uuid=False), ForeignKey("questions.id"), nullable=False, unique=True)

    transcript = Column(Text, nullable=True)             # from Whisper (Phase 3) or typed text (Phase 2)
    relevance_score = Column(Float, nullable=True)
    star_score = Column(JSON, nullable=True)             # {"situation":.., "task":.., "action":.., "result":..}

    # Multimedia signals (Phase 3/4)
    speaking_pace_wpm = Column(Float, nullable=True)
    filler_word_count = Column(Integer, nullable=True)
    voice_confidence_score = Column(Float, nullable=True)
    eye_contact_score = Column(Float, nullable=True)
    facial_expression_score = Column(Float, nullable=True)
    posture_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="answer")
