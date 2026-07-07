from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    User, Resume, JobDescription, InterviewSession, Question, Answer, InterviewStatus,
)
from app.schemas import (
    InterviewSessionCreate, InterviewSessionOut, NextQuestionOut, AnswerSubmit, AnswerOut,
)
from app.services.skill_extractor import extract_resume_skills, extract_jd_requirements, compute_match
from app.services.question_generator import generate_questions
from app.services.answer_evaluator import evaluate_answer

router = APIRouter(prefix="/interviews", tags=["interviews"])

# The LLM's own "needs_followup" judgment is too soft on its own — it tends to
# say yes for almost any answer, since a follow-up can always technically be
# asked. This acts as a hard backstop: even if the model says needs_followup,
# we don't act on it unless the answer actually scored low. Tune as needed.
FOLLOWUP_RELEVANCE_THRESHOLD = 60


def _get_owned_session(session_id: str, db: Session, current_user: User) -> InterviewSession:
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return session


def _next_unanswered_question(session: InterviewSession) -> Question | None:
    unanswered = [q for q in session.questions if q.answer is None]
    if not unanswered:
        return None
    return sorted(unanswered, key=lambda q: q.order_index)[0]


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


@router.get("/{session_id}/next-question", response_model=NextQuestionOut)
def get_next_question(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_owned_session(session_id, db, current_user)
    next_q = _next_unanswered_question(session)
    return NextQuestionOut(
        completed=next_q is None,
        question=next_q,
        session_status=session.status,
    )


@router.post("/{session_id}/answers", response_model=AnswerOut, status_code=201)
def submit_answer(
    session_id: str,
    payload: AnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_owned_session(session_id, db, current_user)

    question = (
        db.query(Question)
        .filter(Question.id == payload.question_id, Question.session_id == session.id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session")
    if question.answer is not None:
        raise HTTPException(status_code=400, detail="This question has already been answered")

    evaluation = evaluate_answer(
        question_text=question.text,
        answer_text=payload.transcript,
        interview_type=session.interview_type.value,
        topic=question.topic,
        is_followup=bool(question.is_followup),
    )

    answer = Answer(
        question_id=question.id,
        transcript=payload.transcript,
        relevance_score=evaluation["relevance_score"],
        star_score=evaluation["star_score"],
    )
    db.add(answer)

    # Adaptive follow-up: only branch one level deep (don't chain follow-ups
    # off follow-ups) to keep interview length bounded and predictable.
    followup_generated = False
    if (
        evaluation["needs_followup"]
        and evaluation["followup_question"]
        and not question.is_followup
        and evaluation["relevance_score"] < FOLLOWUP_RELEVANCE_THRESHOLD
    ):
        insert_index = question.order_index + 1
        for other in session.questions:
            if other.id != question.id and other.order_index >= insert_index:
                other.order_index += 1

        db.add(Question(
            session_id=session.id,
            text=evaluation["followup_question"],
            order_index=insert_index,
            topic=question.topic,
            is_followup=1,
            parent_question_id=question.id,
        ))
        followup_generated = True

    if session.status in (InterviewStatus.CREATED, InterviewStatus.QUESTIONS_READY):
        session.status = InterviewStatus.IN_PROGRESS

    db.commit()
    db.refresh(session)
    db.refresh(answer)

    next_q = _next_unanswered_question(session)
    if next_q is None and session.status != InterviewStatus.COMPLETED:
        session.status = InterviewStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(session)

    return AnswerOut(
        id=answer.id,
        question_id=answer.question_id,
        transcript=answer.transcript,
        relevance_score=answer.relevance_score,
        star_score=answer.star_score,
        created_at=answer.created_at,
        strengths=evaluation["strengths"],
        weaknesses=evaluation["weaknesses"],
        session_status=session.status,
        followup_generated=followup_generated,
        next_question=next_q,
    )
