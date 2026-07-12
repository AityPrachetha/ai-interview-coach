"""
Phase 2 — evaluates a candidate's typed answer to an interview question.

One Gemini call does double duty:
  1. Scores the answer (relevance, and STAR breakdown if it's a behavioral
     question) with strengths/weaknesses feedback.
  2. Decides whether the answer was weak enough to warrant a follow-up,
     and if so, drafts that follow-up question in the same response —
     this saves a second round trip and lets the follow-up be grounded
     in exactly what the candidate said (not just "ask something similar").

Kept as its own module (separate from question_generator.py) since it's a
distinct concern: initial questions are generated once from resume+JD,
answers are evaluated one at a time as the interview progresses.
"""
from app.services.llm_client import call_json

ANSWER_EVAL_SYSTEM_PROMPT = """You are an expert interviewer evaluating a candidate's spoken/typed \
answer during a mock interview. Respond ONLY with valid JSON, no other text, in exactly this shape:

{
  "relevance_score": 0-100,
  "star_score": {"situation": 0-100, "task": 0-100, "action": 0-100, "result": 0-100} or null,
  "strengths": ["short phrase", ...],
  "weaknesses": ["short phrase", ...],
  "needs_followup": true or false,
  "followup_question": "..." or null
}

Rules:
- "relevance_score" is a holistic answer-quality score, NOT just "did they mention the right topic."
  Score 90-100 ONLY for answers that are on-topic AND concise AND specific/tailored (concrete
  details, no filler, nothing a generic candidate could paste into any interview). Deduct
  meaningfully for:
    * rambling or padding — restating the same point in different words, going well beyond what
      the question needed
    * genericness — could this answer be copy-pasted into a different company's interview
      unchanged? If yes, that's a real weakness, not a minor one
    * vagueness — claims without specifics (e.g. "I want to learn best practices" with no concrete
      example of what that means in context)
    * not actually using the specific details the question surfaced (e.g. the question references
      the candidate's own project or background and the answer doesn't meaningfully engage with it)
  A well-structured, concise, specific answer should score higher than a long, generic-but-on-topic
  one even if the long one technically "covers everything" — do not default to a high score just
  because the answer is lengthy and topically on-target.
- "star_score" is ONLY populated for BEHAVIORAL questions that expect a Situation/Task/Action/Result
  answer. Score each component on how clearly the candidate covered it. For HR or TECHNICAL
  questions (or any question that isn't a STAR-style scenario), set "star_score" to null.
- "strengths" and "weaknesses" are 1-4 short bullet phrases each, specific to this answer (not
  generic advice). If the answer is long-winded, generic, or under-specific, that MUST appear in
  "weaknesses" — don't let strong topical coverage hide those issues.
- Set "needs_followup" to true if the answer is vague, incomplete, avoids the actual question,
  is missing a key STAR component (for behavioral questions), or a strong interviewer would
  naturally probe deeper. Set it to false if the answer is clear and sufficiently complete —
  in that case the interview should move on to the next topic rather than dwell here.
- If "needs_followup" is true, "followup_question" must be a single, natural, specific follow-up
  that references what the candidate actually said (e.g. asks them to quantify a result they
  mentioned, clarify their specific role, or address the part of the question they skipped).
  If "needs_followup" is false, "followup_question" must be null."""


def evaluate_answer(
    question_text: str,
    answer_text: str,
    interview_type: str,
    topic: str | None,
    is_followup: bool,
) -> dict:
    user_prompt = (
        f"Interview type: {interview_type}\n"
        f"Question topic: {topic or 'general'}\n"
        f"This question is itself a follow-up: {is_followup}\n\n"
        f"Question asked:\n{question_text}\n\n"
        f"Candidate's answer:\n{answer_text or '(no answer provided)'}"
    )
    result = call_json(ANSWER_EVAL_SYSTEM_PROMPT, user_prompt)

    # Defensive defaults in case the model omits a field despite the schema prompt
    result.setdefault("relevance_score", 0)
    result.setdefault("star_score", None)
    result.setdefault("strengths", [])
    result.setdefault("weaknesses", [])
    result.setdefault("needs_followup", False)
    result.setdefault("followup_question", None)
    return result
