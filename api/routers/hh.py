import json
import time
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException

from api.config import settings

router = APIRouter(prefix="/hh", tags=["hh"])

TOKEN_CACHE = Path("/tmp/hh_app_token_api.json")


@router.get("/app-token")
def app_access_token():
    """Токен приложения HH (client_credentials) для публичного поиска вакансий."""
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise HTTPException(
            status_code=503,
            detail="HH_CLIENT_ID и HH_CLIENT_SECRET не заданы в .env",
        )
    if TOKEN_CACHE.exists():
        data = json.loads(TOKEN_CACHE.read_text())
        return {"access_token": data["access_token"]}

    resp = requests.post(
        "https://api.hh.ru/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Не удалось получить токен HH")
    token_data = resp.json()
    TOKEN_CACHE.write_text(json.dumps({"access_token": token_data["access_token"]}))
    return {"access_token": token_data["access_token"]}
