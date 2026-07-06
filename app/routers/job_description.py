from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, JobDescription
from app.schemas import JobDescriptionCreate, JobDescriptionOut
from app.services.skill_extractor import extract_jd_requirements

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


@router.post("", response_model=JobDescriptionOut, status_code=201)
def create_job_description(
    payload: JobDescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        extracted_requirements = extract_jd_requirements(payload.raw_text)
    except Exception:
        extracted_requirements = None

    jd = JobDescription(
        user_id=current_user.id,
        title=payload.title,
        company=payload.company,
        raw_text=payload.raw_text,
        extracted_requirements=extracted_requirements,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


@router.get("/{jd_id}", response_model=JobDescriptionOut)
def get_job_description(
    jd_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jd = (
        db.query(JobDescription)
        .filter(JobDescription.id == jd_id, JobDescription.user_id == current_user.id)
        .first()
    )
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    return jd
