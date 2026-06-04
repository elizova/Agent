from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import SavedResume, User
from api.schemas import ResumeIn, ResumeOut

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@router.get("", response_model=list[ResumeOut])
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(SavedResume)
        .filter(SavedResume.user_id == user.id)
        .order_by(SavedResume.updated_at.desc())
        .all()
    )
    return [
        ResumeOut(
            id=r.id,
            name=r.name,
            created_at=str(r.created_at),
            updated_at=str(r.updated_at),
        )
        for r in rows
    ]


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SavedResume)
        .filter(SavedResume.id == resume_id, SavedResume.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Резюме не найдено")
    return ResumeOut(
        id=row.id,
        name=row.name,
        body=row.body,
        created_at=str(row.created_at),
        updated_at=str(row.updated_at),
    )


@router.post("", response_model=ResumeOut)
def create_resume(
    data: ResumeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = _now()
    row = SavedResume(
        user_id=user.id,
        name=data.name,
        body=data.body,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ResumeOut(id=row.id, name=row.name, body=row.body, created_at=now, updated_at=now)


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: int,
    data: ResumeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SavedResume)
        .filter(SavedResume.id == resume_id, SavedResume.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Резюме не найдено")
    now = _now()
    row.name = data.name
    row.body = data.body
    row.updated_at = now
    db.commit()
    return ResumeOut(id=row.id, name=row.name, body=row.body, updated_at=now)


@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SavedResume)
        .filter(SavedResume.id == resume_id, SavedResume.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Резюме не найдено")
    db.delete(row)
    db.commit()
    return {"ok": True}
