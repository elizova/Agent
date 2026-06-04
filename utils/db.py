import streamlit as st

from utils import api_client


def _token() -> str:
    token = st.session_state.get("auth_token")
    if not token:
        raise api_client.ApiError("Войдите в аккаунт (страница «Вход»)")
    return token


def init_db():
    pass


def save_search(
    user_query: str,
    params: dict,
    found_count: int,
    results_count: int,
    resume_preview: str = "",
) -> int:
    return api_client.save_search(
        _token(),
        user_query,
        params,
        found_count,
        results_count,
        resume_preview,
    )


def save_analysis(
    vacancy_id: str,
    vacancy_title: str,
    source: str,
    requirements: dict,
    comparison: dict,
    ats_before: int,
    ats_after: int | None,
    resume_original: str,
    resume_adapted: str = "",
    vacancy_url: str = "",
) -> dict:
    text = (resume_adapted or "").strip()
    meta = api_client.save_analysis(
        _token(),
        vacancy_id=vacancy_id,
        vacancy_title=vacancy_title,
        source=source,
        requirements=requirements,
        comparison=comparison,
        ats_before=ats_before,
        ats_after=ats_after,
        resume_original=resume_original,
        resume_adapted=text,
        vacancy_url=vacancy_url,
    )
    if text and meta.get("id") and not meta.get("saved"):
        meta = api_client.patch_analysis_resume(_token(), meta["id"], text)
    return meta


def get_search_history(limit: int = 15) -> list[dict]:
    return api_client.get_search_history(_token(), limit)


def get_search_history_optional(limit: int = 15) -> list[dict]:
    if not st.session_state.get("auth_token"):
        return []
    try:
        return get_search_history(limit)
    except api_client.ApiError:
        return []


def get_search_session(session_id: int) -> dict | None:
    return api_client.get_search_session(_token(), session_id)


def get_analysis_history(limit: int = 15) -> list[dict]:
    return api_client.get_analysis_history(_token(), limit)


def get_analysis_detail(analysis_id: int) -> dict | None:
    return api_client.get_analysis_detail(_token(), analysis_id)


def get_analysis_history_optional(limit: int = 15) -> list[dict]:
    if not st.session_state.get("auth_token"):
        return []
    try:
        return get_analysis_history(limit)
    except api_client.ApiError:
        return []


def list_saved_resumes() -> list[dict]:
    return api_client.list_saved_resumes(_token())


def list_saved_resumes_optional() -> list[dict]:
    if not st.session_state.get("auth_token"):
        return []
    try:
        return list_saved_resumes()
    except api_client.ApiError:
        return []


def get_saved_resume(resume_id: int) -> dict | None:
    return api_client.get_saved_resume(_token(), resume_id)


def save_resume_record(
    name: str, body: str, resume_id: int | None = None
) -> int:
    return api_client.save_resume_record(_token(), name, body, resume_id)


def delete_resume_record(resume_id: int):
    api_client.delete_resume_record(_token(), resume_id)
