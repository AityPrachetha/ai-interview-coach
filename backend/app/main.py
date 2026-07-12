from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, resume, job_description, interview

# Phase 1: create tables directly from models. Swap to Alembic migrations
# once the schema stabilizes and you need versioned migrations for prod.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Interview Coach API",
    description="Backend for the AI-powered mock interview system (Phase 1: resume/JD intake + skill matching + question generation)",
    version="0.1.0",
)

# Always allow local dev regardless of what FRONTEND_URL is set to, so
# switching FRONTEND_URL to a production URL doesn't accidentally lock out
# local development. In production, set FRONTEND_URL to your deployed
# frontend's URL (e.g. https://ai-interview-coach.vercel.app) via env var -
# no code change needed to go from local to prod or between environments.
_allowed_origins = {"http://localhost:5173", settings.frontend_url}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(job_description.router)
app.include_router(interview.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
