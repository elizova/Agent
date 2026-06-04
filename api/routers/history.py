import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import SearchSession, User, VacancyAnalysis
from api.schemas import AnalysisResumePatchIn, AnalysisSaveIn, SearchSaveIn

router = APIRouter(prefix="/history", tags=["history"])


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


@router.get("/searches")
def list_searches(
    limit: int = 15,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SearchSession)
        .filter(SearchSession.user_id == user.id)
        .order_by(SearchSession.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "user_query": r.user_query,
            "params_json": r.params_json,
            "found_count": r.found_count,
            "results_count": r.results_count,
            "resume_preview": r.resume_preview,
        }
        for r in rows
    ]


@router.get("/searches/{session_id}")
def get_search(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SearchSession)
        .filter(SearchSession.id == session_id, SearchSession.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404)
    return {
        "id": row.id,
        "created_at": row.created_at,
        "user_query": row.user_query,
        "params_json": row.params_json,
        "found_count": row.found_count,
        "results_count": row.results_count,
        "resume_preview": row.resume_preview,
    }


@router.post("/searches")
def save_search(
    data: SearchSaveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = SearchSession(
        user_id=user.id,
        created_at=_ts(),
        user_query=data.user_query,
        params_json=json.dumps(data.params, ensure_ascii=False),
        found_count=data.found_count,
        results_count=data.results_count,
        resume_preview=(data.resume_preview or "")[:500],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.get("/analyses")
def list_analyses(
    limit: int = 15,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(VacancyAnalysis)
        .filter(VacancyAnalysis.user_id == user.id)
        .order_by(VacancyAnalysis.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "vacancy_id": r.vacancy_id,
            "vacancy_title": r.vacancy_title,
            "vacancy_url": r.vacancy_url,
            "source": r.source,
            "ats_before": r.ats_before,
            "ats_after": r.ats_after,
            "resume_adapted": r.resume_adapted or "",
        }
        for r in rows
    ]


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(VacancyAnalysis)
        .filter(
            VacancyAnalysis.id == analysis_id,
            VacancyAnalysis.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404)
    return {
        "id": row.id,
        "created_at": row.created_at,
        "vacancy_id": row.vacancy_id,
        "vacancy_title": row.vacancy_title,
        "vacancy_url": row.vacancy_url,
        "source": row.source,
        "ats_before": row.ats_before,
        "ats_after": row.ats_after,
        "resume_adapted": row.resume_adapted or "",
        "resume_original": row.resume_original or "",
    }


@router.post("/analyses")
def save_analysis(
    data: AnalysisSaveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adapted_text = (data.resume_adapted or "").strip()[:8000]
    row = VacancyAnalysis(
        user_id=user.id,
        created_at=_ts(),
        vacancy_id=data.vacancy_id,
        vacancy_title=data.vacancy_title,
        vacancy_url=data.vacancy_url or "",
        source=data.source,
        requirements_json=json.dumps(data.requirements, ensure_ascii=False),
        comparison_json=json.dumps(data.comparison, ensure_ascii=False),
        ats_before=data.ats_before,
        ats_after=data.ats_after,
        resume_original=(data.resume_original or "")[:3000],
        resume_adapted=adapted_text,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "received_len": len(adapted_text),
        "resume_adapted_len": len(row.resume_adapted or ""),
        "saved": bool((row.resume_adapted or "").strip()),
    }


@router.patch("/analyses/{analysis_id}/resume")
def patch_analysis_resume(
    analysis_id: int,
    data: AnalysisResumePatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(VacancyAnalysis)
        .filter(
            VacancyAnalysis.id == analysis_id,
            VacancyAnalysis.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404)
    row.resume_adapted = data.resume_adapted.strip()[:8000]
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "resume_adapted_len": len(row.resume_adapted or ""),
        "saved": bool((row.resume_adapted or "").strip()),
    }
