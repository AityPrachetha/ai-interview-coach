"""
Uses Gemini to:
  1. Extract structured skills/experience from resume text
  2. Extract required/preferred skills from a job description
  3. Compute a resume-to-JD match score with matched/missing breakdown

Kept as pure functions (no DB access) so they're easy to unit test
and reuse from the interview-session router.
"""
from app.services.llm_client import call_json

RESUME_SKILL_SYSTEM_PROMPT = """You are an expert technical recruiter. Extract structured \
information from the resume text provided. Respond ONLY with valid JSON, no other text, \
in exactly this shape:

{
  "skills": ["skill1", "skill2", ...],
  "years_experience_total": <number or null>,
  "job_titles": ["most recent title", ...],
  "education": ["degree - institution", ...],
  "notable_projects": ["short project description", ...]
}

Include both hard/technical skills (languages, frameworks, tools) and relevant soft skills \
(e.g. "team leadership", "stakeholder communication") if clearly evidenced. Do not invent \
skills that aren't supported by the text."""

JD_REQUIREMENTS_SYSTEM_PROMPT = """You are an expert technical recruiter. Extract structured \
requirements from the job description provided. Respond ONLY with valid JSON, no other text, \
in exactly this shape:

{
  "required_skills": ["skill1", "skill2", ...],
  "nice_to_have_skills": ["skill1", ...],
  "min_years_experience": <number or null>,
  "role_title": "<inferred title or null>",
  "seniority_level": "<junior|mid|senior|lead|null>"
}"""

MATCH_SYSTEM_PROMPT = """You are an expert technical recruiter comparing a candidate's resume \
against a job description's requirements. Respond ONLY with valid JSON, no other text, in \
exactly this shape:

{
  "match_score": <number 0-100>,
  "matched_skills": ["skill", ...],
  "missing_required_skills": ["skill", ...],
  "missing_nice_to_have_skills": ["skill", ...],
  "experience_gap_notes": "<short note or null>",
  "summary": "<2-3 sentence summary of overall fit>"
}

Score generously for closely related/transferable skills (e.g. "Django" partially \
satisfies "Flask" if no exact match), but be honest about hard gaps in required skills."""


def extract_resume_skills(resume_text: str) -> dict:
    return call_json(RESUME_SKILL_SYSTEM_PROMPT, resume_text)


def extract_jd_requirements(jd_text: str) -> dict:
    return call_json(JD_REQUIREMENTS_SYSTEM_PROMPT, jd_text)


def compute_match(resume_skills: dict, jd_requirements: dict) -> dict:
    user_prompt = (
        f"Candidate profile:\n{resume_skills}\n\n"
        f"Job requirements:\n{jd_requirements}"
    )
    return call_json(MATCH_SYSTEM_PROMPT, user_prompt)
