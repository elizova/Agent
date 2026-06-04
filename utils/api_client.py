import os

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 60.0


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _headers(token: str | None) -> dict:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _request(method: str, path: str, token: str | None = None, **kwargs):
    url = f"{API_URL}{path}"
    try:
        r = httpx.request(
            method, url, headers=_headers(token), timeout=TIMEOUT, **kwargs
        )
    except httpx.ConnectError as e:
        raise ApiError(
            f"API недоступен ({API_URL}). Запустите: docker compose up -d",
        ) from e
    if r.status_code >= 400:
        detail = r.text or f"HTTP {r.status_code}"
        if r.content:
            try:
                body = r.json()
                detail = body.get("detail", detail)
                if isinstance(detail, list) and detail:
                    detail = detail[0].get("msg", str(detail[0]))
            except Exception:
                detail = (r.text or detail)[:500]
        raise ApiError(str(detail), r.status_code)
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


def register(
    email: str, password: str, display_name: str | None = None
) -> str:
    data = _request(
        "POST",
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )
    return data["access_token"]


def login(email: str, password: str) -> str:
    data = _request(
        "POST", "/auth/login", json={"email": email, "password": password}
    )
    return data["access_token"]


def me(token: str) -> dict:
    return _request("GET", "/auth/me", token=token)


def save_hh_token(
    token: str, access_token: str, refresh_token: str, expires_at: float
):
    _request(
        "POST",
        "/auth/hh",
        token=token,
        json={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        },
    )


def hh_status(token: str) -> dict:
    return _request("GET", "/auth/hh/status", token=token)


def get_hh_tokens(token: str) -> dict:
    return _request("GET", "/auth/hh/tokens", token=token)


def disconnect_hh(token: str):
    _request("DELETE", "/auth/hh", token=token)


def get_app_hh_token() -> str:
    return _request("GET", "/hh/app-token")["access_token"]


def list_saved_resumes(token: str) -> list[dict]:
    return _request("GET", "/resumes", token=token)


def get_saved_resume(token: str, resume_id: int) -> dict | None:
    try:
        return _request("GET", f"/resumes/{resume_id}", token=token)
    except ApiError as e:
        if e.status_code == 404:
            return None
        raise


def save_resume_record(
    token: str, name: str, body: str, resume_id: int | None = None
) -> int:
    if resume_id:
        _request(
            "PUT",
            f"/resumes/{resume_id}",
            token=token,
            json={"name": name, "body": body},
        )
        return resume_id
    data = _request(
        "POST", "/resumes", token=token, json={"name": name, "body": body}
    )
    return data["id"]


def delete_resume_record(token: str, resume_id: int):
    _request("DELETE", f"/resumes/{resume_id}", token=token)


def save_search(
    token: str,
    user_query: str,
    params: dict,
    found_count: int,
    results_count: int,
    resume_preview: str = "",
) -> int:
    data = _request(
        "POST",
        "/history/searches",
        token=token,
        json={
            "user_query": user_query,
            "params": params,
            "found_count": found_count,
            "results_count": results_count,
            "resume_preview": resume_preview,
        },
    )
    return data["id"]


def save_analysis(token: str, **kwargs) -> dict:
    return _request("POST", "/history/analyses", token=token, json=kwargs)


def patch_analysis_resume(
    token: str, analysis_id: int, resume_adapted: str
) -> dict:
    return _request(
        "PATCH",
        f"/history/analyses/{analysis_id}/resume",
        token=token,
        json={"resume_adapted": resume_adapted},
    )


def get_search_history(token: str, limit: int = 15) -> list[dict]:
    return _request("GET", f"/history/searches?limit={limit}", token=token)


def get_search_session(token: str, session_id: int) -> dict | None:
    try:
        return _request("GET", f"/history/searches/{session_id}", token=token)
    except ApiError as e:
        if e.status_code == 404:
            return None
        raise


def get_analysis_history(token: str, limit: int = 15) -> list[dict]:
    return _request("GET", f"/history/analyses?limit={limit}", token=token)


def get_analysis_detail(token: str, analysis_id: int) -> dict | None:
    try:
        return _request("GET", f"/history/analyses/{analysis_id}", token=token)
    except ApiError as e:
        if e.status_code == 404:
            return None
        raise
