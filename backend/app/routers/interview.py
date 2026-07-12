import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    User, Resume, JobDescription, InterviewSession, Question, Answer, VisionSample, InterviewStatus,
)
from app.schemas import (
    InterviewSessionCreate, InterviewSessionOut, NextQuestionOut, AnswerSubmit, AnswerOut, FrameAnalysisOut,
    InterviewReportOut, QuestionAnswerSummary,
)
from app.services.skill_extractor import extract_resume_skills, extract_jd_requirements, compute_match
from app.services.question_generator import generate_questions
from app.services.answer_evaluator import evaluate_answer
from app.services.speech_to_text import transcribe_audio
from app.services.voice_analysis import analyze_voice
from app.services.vision_analysis import analyze_frame
from app.services.report_generator import generate_report, compute_weight_coverage

router = APIRouter(prefix="/interviews", tags=["interviews"])

# The LLM's own "needs_followup" judgment is too soft on its own — it tends to
# say yes for almost any answer, since a follow-up can always technically be
# asked. This acts as a hard backstop: even if the model says needs_followup,
# we don't act on it unless the answer actually scored low. Tune as needed.
FOLLOWUP_RELEVANCE_THRESHOLD = 60
# The LLM's own "needs_followup" judgment is too soft on its own — it tends to
# say yes for almost any answer, since a follow-up can always technically be
# asked. This acts as a hard backstop: even if the model says needs_followup,
# we don't act on it unless the answer actually scored low. Tune as needed.

MAX_BASE_QUESTIONS = 7
"""
Hard ceiling on the initial question set, enforced in code rather than
trusted to the prompt. The question_generator prompt asks for "6-8
questions" but that's a prose instruction with zero enforcement - different
LLM providers (this app can fall back from Gemini to Groq to OpenRouter)
follow numeric instructions with very different fidelity, so a model
ignoring the range and returning e.g. 14 was always a real risk. Slicing
here means the total interview length stays predictable regardless of
which provider actually answered.
"""

MAX_FOLLOWUPS_PER_SESSION = 3
"""
Independent of the existing per-question depth cap (no follow-up ever
spawns a follow-up of its own), this caps how many follow-ups can
accumulate across an ENTIRE session. Without this, tightening the
evaluator's scoring rubric (so more answers legitimately score below
FOLLOWUP_RELEVANCE_THRESHOLD) can silently double the total interview
length - e.g. 7 base questions + up to 7 follow-ups = 14, which is exactly
the kind of ballooning this exists to prevent.
"""


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
    generated = generated[:MAX_BASE_QUESTIONS]

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


def _average(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 1)


def _score_and_save_answer(
    session: InterviewSession,
    question: Question,
    transcript: str,
    db: Session,
    voice_metrics: dict | None = None,
) -> AnswerOut:
    """
    Shared by both the text-answer and audio-answer endpoints: scores the
    transcript via the LLM, saves the Answer row (with voice metrics if this
    came from an audio submission), applies the adaptive follow-up logic,
    and advances session status. Keeping this in one place means the
    scoring/follow-up/status rules can't drift between the two input paths.

    Also folds in any webcam VisionSample rows captured while this question
    was being answered (Phase 4) — averaged across frames where a face/pose
    was actually detected, so a candidate briefly stepping out of frame
    doesn't drag the score down.

    A blank/whitespace-only transcript (silent audio, or an empty typed
    submission) is short-circuited to a deterministic zero-score evaluation
    WITHOUT calling the LLM — cheaper than an API call for a trivial case,
    and more reliable than hoping the model scores an empty string as 0.
    It still flows through the normal save/follow-up/status logic below, so
    the candidate gets a follow-up prompt to try again rather than the
    request just failing outright.
    """
    is_blank = not (transcript or "").strip()
    if is_blank:
        evaluation = {
            "relevance_score": 0,
            "star_score": None,
            "strengths": [],
            "weaknesses": ["No answer was detected — nothing was said or typed."],
            "needs_followup": True,
            "followup_question": (
                None if question.is_followup
                else f"It looks like no answer came through. Let's try again: {question.text}"
            ),
        }
    else:
        evaluation = evaluate_answer(
            question_text=question.text,
            answer_text=transcript,
            interview_type=session.interview_type.value,
            topic=question.topic,
            is_followup=bool(question.is_followup),
        )

    answer = Answer(
        question_id=question.id,
        transcript=transcript,
        relevance_score=evaluation["relevance_score"],
        star_score=evaluation["star_score"],
    )
    if voice_metrics:
        answer.speaking_pace_wpm = voice_metrics.get("speaking_pace_wpm")
        answer.filler_word_count = voice_metrics.get("filler_word_count")
        answer.voice_confidence_score = voice_metrics.get("voice_confidence_score")

    vision_samples = db.query(VisionSample).filter(VisionSample.question_id == question.id).all()
    if vision_samples:
        answer.eye_contact_score = _average([s.eye_contact_score for s in vision_samples])
        answer.facial_expression_score = _average([s.facial_expression_score for s in vision_samples])
        answer.posture_score = _average([s.posture_score for s in vision_samples])

    db.add(answer)

    # Adaptive follow-up: only branch one level deep (don't chain follow-ups
    # off follow-ups) to keep interview length bounded and predictable. The
    # relevance-score check is a hard backstop — the LLM's own
    # "needs_followup" judgment tends to say yes for almost any answer, since
    # a follow-up can technically always be asked; we only act on it when the
    # answer actually scored low.
    followup_generated = False
    existing_followup_count = sum(1 for q in session.questions if q.is_followup)
    if (
        evaluation["needs_followup"]
        and evaluation["followup_question"]
        and not question.is_followup
        and evaluation["relevance_score"] < FOLLOWUP_RELEVANCE_THRESHOLD
        and existing_followup_count < MAX_FOLLOWUPS_PER_SESSION
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
        speaking_pace_wpm=answer.speaking_pace_wpm,
        filler_word_count=answer.filler_word_count,
        voice_confidence_score=answer.voice_confidence_score,
        eye_contact_score=answer.eye_contact_score,
        facial_expression_score=answer.facial_expression_score,
        posture_score=answer.posture_score,
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

    return _score_and_save_answer(session=session, question=question, transcript=payload.transcript, db=db)


@router.post("/{session_id}/answers/audio", response_model=AnswerOut, status_code=201)
async def submit_answer_audio(
    session_id: str,
    question_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Same as POST /answers, but the candidate's answer comes in as a recorded
    audio file instead of typed text. Transcribes via Whisper, derives
    speaking-pace/filler-word/confidence signals from the transcript +
    timings, then runs through the exact same scoring/follow-up pipeline as
    a typed answer.

    Accepts whatever audio container Whisper/ffmpeg can decode (webm, wav,
    mp3, m4a, ogg — a browser's MediaRecorder output works fine).
    """
    session = _get_owned_session(session_id, db, current_user)

    question = (
        db.query(Question)
        .filter(Question.id == question_id, Question.session_id == session.id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session")
    if question.answer is not None:
        raise HTTPException(status_code=400, detail="This question has already been answered")

    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        stt_result = transcribe_audio(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Silent/undecodable audio -> transcribe_audio already returns an empty
    # string rather than raising (see speech_to_text.py). Rather than
    # failing the request here, let it flow through to
    # _score_and_save_answer's blank-transcript short-circuit below, which
    # scores it 0 and offers a follow-up instead of blocking the interview.

    voice_metrics = analyze_voice(stt_result["text"], stt_result["segments"], stt_result["duration"])

    return _score_and_save_answer(
        session=session,
        question=question,
        transcript=stt_result["text"],
        db=db,
        voice_metrics=voice_metrics,
    )


@router.post("/{session_id}/questions/{question_id}/frames", response_model=FrameAnalysisOut, status_code=201)
async def submit_webcam_frame(
    session_id: str,
    question_id: str,
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts ONE webcam frame at a time, captured periodically (recommended:
    every 1-2 seconds) while the candidate is answering `question_id` —
    not a continuous video stream. Streaming full video through this
    backend would be both a bandwidth and latency problem; sampling
    keeps per-frame processing fast enough for near-real-time feedback.

    Returns the per-frame scores immediately so the frontend can show live
    signals (e.g. a "look at the camera" nudge). The samples are also
    stored and get averaged into the Answer's eye_contact_score /
    facial_expression_score / posture_score once the question is answered
    via POST /answers or /answers/audio — call this endpoint as many times
    as you like before that happens.
    """
    session = _get_owned_session(session_id, db, current_user)

    question = (
        db.query(Question)
        .filter(Question.id == question_id, Question.session_id == session.id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session")
    if question.answer is not None:
        raise HTTPException(status_code=400, detail="This question has already been answered")

    image_bytes = await frame.read()
    result = analyze_frame(image_bytes)

    db.add(VisionSample(
        question_id=question.id,
        face_detected=1 if result["face_detected"] else 0,
        eye_contact_score=result["eye_contact_score"],
        facial_expression_score=result["facial_expression_score"],
        posture_score=result["posture_score"],
    ))
    db.commit()

    return FrameAnalysisOut(**result)


@router.get("/{session_id}/report", response_model=InterviewReportOut)
def get_interview_report(
    session_id: str,
    recompute: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the aggregated hiring-readiness report for this session.
    Cached on the InterviewSession row after first computation (the LLM
    call for improvement suggestions is the expensive part) — pass
    ?recompute=true to force regeneration, e.g. after answering more
    questions in a session that was previously reported on early.
    """
    session = _get_owned_session(session_id, db, current_user)

    answers = [q.answer for q in session.questions if q.answer is not None]
    if not answers:
        raise HTTPException(status_code=400, detail="No answered questions yet — nothing to report on.")

    if recompute or session.hiring_readiness_score is None:
        report = generate_report(session, answers)
        session.communication_score = report["communication_score"]
        session.confidence_score = report["confidence_score"]
        session.technical_score = report["technical_score"]
        session.behavioral_score = report["behavioral_score"]
        session.hiring_readiness_score = report["hiring_readiness_score"]
        session.improvement_suggestions = report["improvement_suggestions"]
        db.commit()
        db.refresh(session)
        per_question = report["per_question"]
    else:
        # Cached path still recomputes the per-question breakdown fresh —
        # it's cheap (no LLM call) and always reflects the current DB state.
        per_question = [
            {
                "question_id": a.question.id,
                "question_text": a.question.text,
                "topic": a.question.topic,
                "is_followup": bool(a.question.is_followup),
                "transcript": a.transcript,
                "relevance_score": a.relevance_score,
                "star_score": a.star_score,
                "speaking_pace_wpm": a.speaking_pace_wpm,
                "filler_word_count": a.filler_word_count,
                "voice_confidence_score": a.voice_confidence_score,
                "eye_contact_score": a.eye_contact_score,
                "facial_expression_score": a.facial_expression_score,
                "posture_score": a.posture_score,
            }
            for a in answers
        ]

    return InterviewReportOut(
        session_id=session.id,
        session_status=session.status,
        is_preliminary=session.status != InterviewStatus.COMPLETED,
        questions_answered=len(answers),
        total_questions=len(session.questions),
        weight_coverage=compute_weight_coverage({
            "communication_score": session.communication_score,
            "confidence_score": session.confidence_score,
            "technical_score": session.technical_score,
            "behavioral_score": session.behavioral_score,
            "resume_match_score": session.resume_match_score,
        }),
        communication_score=session.communication_score,
        confidence_score=session.confidence_score,
        technical_score=session.technical_score,
        behavioral_score=session.behavioral_score,
        resume_match_score=session.resume_match_score,
        hiring_readiness_score=session.hiring_readiness_score,
        improvement_suggestions=session.improvement_suggestions or [],
        questions=[QuestionAnswerSummary(**q) for q in per_question],
    )
