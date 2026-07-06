from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Resume, JobDescription, InterviewSession, Question, InterviewStatus
from app.schemas import InterviewSessionCreate, InterviewSessionOut
from app.services.skill_extractor import extract_resume_skills, extract_jd_requirements, compute_match
from app.services.question_generator import generate_questions

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", response_model=InterviewSessionOut, status_code=201)
def create_interview_session(
    payload: InterviewSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == payload.resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    jd = (
        db.query(JobDescription)
        .filter(JobDescription.id == payload.job_description_id, JobDescription.user_id == current_user.id)
        .first()
    )
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")

    # Re-extract on the fly if either extraction failed earlier (e.g. LLM hiccup on upload)
    resume_skills = resume.extracted_skills or extract_resume_skills(resume.raw_text)
    jd_requirements = jd.extracted_requirements or extract_jd_requirements(jd.raw_text)

    match_result = compute_match(resume_skills, jd_requirements)

    session = InterviewSession(
        user_id=current_user.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        interview_type=payload.interview_type,
        status=InterviewStatus.CREATED,
        resume_match_score=match_result.get("match_score"),
        skill_match_details=match_result,
    )
    db.add(session)
    db.flush()  # get session.id before generating questions

    generated = generate_questions(
        resume_skills=resume_skills,
        jd_requirements=jd_requirements,
        match_result=match_result,
        interview_type=payload.interview_type.value,
    )

    for idx, q in enumerate(generated):
        db.add(Question(
            session_id=session.id,
            text=q["text"],
            order_index=idx,
            topic=q.get("topic"),
            is_followup=0,
        ))

    session.status = InterviewStatus.QUESTIONS_READY
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=InterviewSessionOut)
def get_interview_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return session
