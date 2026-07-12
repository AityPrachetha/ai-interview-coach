from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
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
