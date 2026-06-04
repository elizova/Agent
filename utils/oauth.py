import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

import requests


def _hh_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_hh_client_id() -> str:
    return _hh_env("HH_CLIENT_ID")


def get_hh_client_secret() -> str:
    return _hh_env("HH_CLIENT_SECRET")


def get_hh_redirect_uri() -> str:
    return _hh_env("HH_REDIRECT_URI", "http://localhost:8501")


AUTH_URL = "https://hh.ru/oauth/authorize"
TOKEN_URL = "https://api.hh.ru/token"

STORAGE_DIR = Path("/tmp/hh_oauth_states")
STORAGE_DIR.mkdir(exist_ok=True)

TOKEN_FILE = Path("/tmp/hh_app_token.json")


def get_app_access_token():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return data["access_token"]

    payload = {
        "grant_type": "client_credentials",
        "client_id": get_hh_client_id(),
        "client_secret": get_hh_client_secret(),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": access_token}, f)
        return access_token
    else:
        raise Exception(
            f"Ошибка получения токена приложения: {response.status_code} {response.text}"
        )


def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)
    sha256 = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(sha256).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _read_state_data(state: str) -> dict | None:
    state_file = STORAGE_DIR / f"{state}.json"
    if not state_file.exists():
        return None
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def peek_app_jwt_from_state(state: str) -> str | None:
    data = _read_state_data(state)
    if not data:
        return None
    jwt = (data.get("app_jwt") or "").strip()
    return jwt or None


def get_auth_url(redirect_uri=None, app_jwt: str | None = None):
    if redirect_uri is None:
        redirect_uri = get_hh_redirect_uri()
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_hex(16)

    state_file = STORAGE_DIR / f"{state}.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "code_verifier": code_verifier,
                "timestamp": time.time(),
                "app_jwt": app_jwt or "",
            },
            f,
        )

    params = {
        "response_type": "code",
        "client_id": get_hh_client_id(),
        "state": state,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{AUTH_URL}?{query_string}", state, code_verifier


def exchange_code_for_token(code, state, redirect_uri=None):
    if redirect_uri is None:
        redirect_uri = get_hh_redirect_uri()

    state_file = STORAGE_DIR / f"{state}.json"
    if not state_file.exists():
        raise Exception("Состояние авторизации не найдено или истекло.")
    with open(state_file, "r") as f:
        data = json.load(f)
        code_verifier = data["code_verifier"]
    os.remove(state_file)

    payload = {
        "grant_type": "authorization_code",
        "client_id": get_hh_client_id(),
        "client_secret": get_hh_client_secret(),
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        return token_data
    else:
        raise Exception(
            f"Ошибка обмена токена: {response.status_code} {response.text}"
        )


def refresh_access_token(refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "client_id": get_hh_client_id(),
        "client_secret": get_hh_client_secret(),
        "refresh_token": refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Ошибка обновления токена: {response.status_code} {response.text}"
        )


def cleanup_old_states(expire_seconds=300):
    now = time.time()
    for f in STORAGE_DIR.glob("*.json"):
        if now - f.stat().st_mtime > expire_seconds:
            os.remove(f)
