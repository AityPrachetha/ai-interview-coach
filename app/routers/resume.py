import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User, Resume
from app.schemas import ResumeOut
from app.services.resume_parser import extract_text, UnsupportedFileType
from app.services.skill_extractor import extract_resume_skills

router = APIRouter(prefix="/resumes", tags=["resumes"])

MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


@router.post("", response_model=ResumeOut, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.max_upload_mb}MB.",
        )

    # 1. Save raw file to disk (swap for S3 upload in production)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}_{file.filename}"
    storage_path = upload_dir / stored_name
    storage_path.write_bytes(file_bytes)

    # 2. Extract text
    try:
        raw_text = extract_text(file_bytes, file.filename)
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 3. Extract structured skills via Gemini
    try:
        extracted_skills = extract_resume_skills(raw_text)
    except Exception as e:
        # Don't fail the whole upload if the LLM call hiccups — save the
        # resume text and let the user retry extraction later.
        extracted_skills = None

    resume = Resume(
        user_id=current_user.id,
        original_filename=file.filename,
        storage_path=str(storage_path),
        raw_text=raw_text,
        extracted_skills=extracted_skills,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.post("/{resume_id}/reextract", response_model=ResumeOut)
def reextract_skills(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retry Gemini skill extraction if it failed or the user wants a refresh."""
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.extracted_skills = extract_resume_skills(resume.raw_text)
    db.commit()
    db.refresh(resume)
    return resume
