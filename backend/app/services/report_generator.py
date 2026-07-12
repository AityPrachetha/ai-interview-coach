"""
Phase 5 — aggregates every signal collected across an interview session
(LLM relevance/STAR scores, voice metrics, vision metrics, resume-JD match)
into a final report: four component scores, one hiring-readiness
composite, and LLM-generated improvement suggestions.

Key design decision: NOT every session will have every signal. A text-only
interview has no voice/vision data; an HR interview has no meaningful
"technical_score"; a candidate who answered everything via typed text has
no confidence_score inputs at all. Rather than defaulting missing signals
to 0 (which would unfairly tank the composite) or faking a number, we:
  - compute each component score only from whatever inputs are actually
    present, returning None if there's nothing to compute from
  - dynamically re-weight the hiring-readiness composite over only the
    components that exist, so a text-only session isn't penalized for
    lacking voice/vision data it was never given a chance to produce
"""
from app.services.llm_client import call_json


def _avg(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 1)


def _compute_communication_score(answers: list) -> float | None:
    """
    Communication quality: how relevant/clear answers were (LLM relevance
    score, all question types) blended with voice delivery signals (pace,
    fillers -> confidence heuristic) where audio answers exist. Weighted
    70/30 relevance-vs-delivery when voice data exists, otherwise pure
    relevance.
    """
    relevance = _avg([a.relevance_score for a in answers])
    if relevance is None:
        return None

    voice_scores = [a.voice_confidence_score for a in answers if a.voice_confidence_score is not None]
    if not voice_scores:
        return relevance

    voice_avg = _avg(voice_scores)
    return round(relevance * 0.7 + voice_avg * 0.3, 1)


def _compute_confidence_score(answers: list) -> float | None:
    """
    Delivery confidence: blends voice confidence (pace/fillers) with visual
    signals (eye contact, posture) where webcam data exists. Returns None
    entirely for sessions with neither — there's nothing to base a
    confidence read on for a plain text interview, and reporting a number
    anyway would be misleading rather than measuring anything real.
    """
    components = []
    voice_avg = _avg([a.voice_confidence_score for a in answers])
    if voice_avg is not None:
        components.append(voice_avg)
    eye_avg = _avg([a.eye_contact_score for a in answers])
    if eye_avg is not None:
        components.append(eye_avg)
    posture_avg = _avg([a.posture_score for a in answers])
    if posture_avg is not None:
        components.append(posture_avg)

    if not components:
        return None
    return round(sum(components) / len(components), 1)


def _compute_technical_score(answers: list, interview_type: str) -> float | None:
    """Only meaningful for TECHNICAL-type sessions; None otherwise."""
    if interview_type != "TECHNICAL":
        return None
    return _avg([a.relevance_score for a in answers])


def _compute_behavioral_score(answers: list) -> float | None:
    """
    Averages STAR component scores across every answer that got a STAR
    breakdown (regardless of overall session interview_type — a HR or
    technical session can still contain a behavioral-style question that
    picked up a star_score).
    """
    star_answers = [a for a in answers if a.star_score]
    if not star_answers:
        return None
    all_components = []
    for a in star_answers:
        all_components.extend([v for v in a.star_score.values() if v is not None])
    return _avg(all_components)


HIRING_READINESS_WEIGHTS = {
    "communication_score": 0.30,
    "confidence_score": 0.20,
    "technical_score": 0.25,
    "behavioral_score": 0.15,
    "resume_match_score": 0.10,
}


def compute_weight_coverage(component_scores: dict) -> float:
    """
    Same present-subset logic as _compute_hiring_readiness, but callable
    on its own — used when serving a CACHED hiring_readiness_score (no LLM
    call, no recompute) but still wanting fresh coverage/question-count
    numbers reflecting the current state of the session.
    """
    present = {k for k, v in component_scores.items() if v is not None}
    return round(sum(HIRING_READINESS_WEIGHTS[k] for k in present), 2)


def _compute_hiring_readiness(component_scores: dict) -> tuple[float | None, float]:
    """
    Weighted composite over whichever component scores are actually
    present. Weights are renormalized over the present subset so a session
    missing e.g. technical_score (HR interview) doesn't get an artificially
    lower composite just for not having that signal to begin with.

    Also returns weight_coverage: the fraction (0-1) of the FULL weighting
    scheme that's actually backed by real data. A session with only
    communication_score present has coverage 0.30 (just that weight) — the
    composite itself doesn't reveal how thin the evidence behind it is,
    so this is surfaced separately for the report to show its work.
    """
    present = {k: v for k, v in component_scores.items() if v is not None}
    if not present:
        return None, 0.0
    total_weight = sum(HIRING_READINESS_WEIGHTS[k] for k in present)
    weighted_sum = sum(present[k] * HIRING_READINESS_WEIGHTS[k] for k in present)
    return round(weighted_sum / total_weight, 1), round(total_weight, 2)


IMPROVEMENT_SYSTEM_PROMPT = """You are an expert interview coach reviewing a candidate's completed mock \
interview. Respond ONLY with valid JSON, no other text, in exactly this shape:

{
  "improvement_suggestions": [
    {"area": "short label, e.g. 'STAR structure' or 'Technical depth'", "suggestion": "1-2 concrete, actionable sentences"},
    ...
  ]
}

Give 3-5 suggestions, ordered by impact (most important first). Ground every suggestion in the
specific weaknesses and question topics provided — do not give generic interview advice that could
apply to anyone. If resume-to-job-description skill gaps are provided, include at least one
suggestion addressing the most important gap."""


def _generate_improvement_suggestions(
    answers: list,
    interview_type: str,
    resume_match_details: dict | None,
) -> list:
    """
    NOTE: per-answer `strengths`/`weaknesses` from the evaluator are never
    persisted to the DB (Answer has no such columns — they only ever
    existed transiently in the AnswerOut API response at submission time).
    So instead of relying on those, this rebuilds context straight from
    what IS persisted: each question's text/topic, the transcript, and the
    relevance/STAR scores. That's enough for the LLM to identify real
    patterns across the interview.
    """
    qa_lines = []
    for a in answers:
        q = a.question
        line = (
            f"Q ({q.topic or 'general'}): {q.text}\n"
            f"A: {a.transcript or '(no answer)'}\n"
            f"Relevance score: {a.relevance_score}"
        )
        if a.star_score:
            line += f", STAR breakdown: {a.star_score}"
        qa_lines.append(line)

    skill_gap_note = ""
    if resume_match_details and resume_match_details.get("missing"):
        skill_gap_note = f"Missing skills vs job description: {', '.join(resume_match_details['missing'])}"

    user_prompt = (
        f"Interview type: {interview_type}\n"
        f"{skill_gap_note}\n\n"
        f"Full transcript with scores:\n\n" + "\n\n".join(qa_lines)
    )
    result = call_json(IMPROVEMENT_SYSTEM_PROMPT, user_prompt)
    return result.get("improvement_suggestions", [])


def generate_report(session, answers: list) -> dict:
    """
    `answers` should be the list of Answer objects for this session's
    questions (with `.question` relationship loaded for topic access).
    Returns a dict matching the score fields already on InterviewSession,
    plus a per-answer breakdown for a transparent, explainable report.
    """
    communication_score = _compute_communication_score(answers)
    confidence_score = _compute_confidence_score(answers)
    technical_score = _compute_technical_score(answers, session.interview_type.value)
    behavioral_score = _compute_behavioral_score(answers)
    resume_match_score = session.resume_match_score

    hiring_readiness_score, weight_coverage = _compute_hiring_readiness({
        "communication_score": communication_score,
        "confidence_score": confidence_score,
        "technical_score": technical_score,
        "behavioral_score": behavioral_score,
        "resume_match_score": resume_match_score,
    })

    improvement_suggestions = _generate_improvement_suggestions(
        answers=answers,
        interview_type=session.interview_type.value,
        resume_match_details=session.skill_match_details,
    )

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

    return {
        "communication_score": communication_score,
        "confidence_score": confidence_score,
        "technical_score": technical_score,
        "behavioral_score": behavioral_score,
        "resume_match_score": resume_match_score,
        "hiring_readiness_score": hiring_readiness_score,
        "weight_coverage": weight_coverage,
        "questions_answered": len(answers),
        "total_questions": len(session.questions),
        "improvement_suggestions": improvement_suggestions,
        "per_question": per_question,
    }
