"""
Generates a personalized set of opening interview questions based on
the candidate's resume, the job description, and the chosen interview
type. Follow-up question generation (adaptive logic) lands in Phase 2
and will live in its own module (question_generator_followup.py) so
this stays focused on the initial question set.
"""
from app.services.llm_client import call_json

QUESTION_GEN_SYSTEM_PROMPT = """You are an expert interviewer preparing questions for a mock \
interview. Given the candidate's resume summary, the job requirements, and the interview type, \
generate 6-8 personalized interview questions. Respond ONLY with valid JSON, no other text, \
in exactly this shape:

{
  "questions": [
    {"text": "...", "topic": "short topic label"},
    ...
  ]
}

Rules:
- HR interviews: focus on motivation, culture fit, career goals, salary/logistics expectations.
- TECHNICAL interviews: focus on the specific skills/technologies in the job requirements and \
resume, mixing conceptual and applied questions. Reference actual projects from the resume \
where possible so it feels personalized rather than generic.
- BEHAVIORAL interviews: use scenarios that can be answered with the STAR method (Situation, \
Task, Action, Result), targeting soft skills relevant to the role (leadership, conflict, \
ambiguity, failure/learning, collaboration).
- Prioritize gaps or unclear areas between the resume and job requirements — those make the \
most useful interview questions.
- Order questions from warm-up (easier) to more challenging."""


def generate_questions(
    resume_skills: dict,
    jd_requirements: dict,
    match_result: dict,
    interview_type: str,
) -> list[dict]:
    user_prompt = (
        f"Interview type: {interview_type}\n\n"
        f"Candidate profile:\n{resume_skills}\n\n"
        f"Job requirements:\n{jd_requirements}\n\n"
        f"Resume-to-JD match analysis:\n{match_result}"
    )
    result = call_json(QUESTION_GEN_SYSTEM_PROMPT, user_prompt)
    return result.get("questions", [])
