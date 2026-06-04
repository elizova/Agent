import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import HHToken, User
from api.schemas import (
    HHTokenIn,
    HHStatusOut,
    LoginIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from api.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user = User(
        email=data.email.lower().strip(),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.email)
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return TokenOut(access_token=create_access_token(user.id, user.email))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/hh", response_model=HHStatusOut)
def save_hh_token(
    data: HHTokenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(HHToken).filter(HHToken.user_id == user.id).first()
    if row:
        row.access_token = data.access_token
        row.refresh_token = data.refresh_token
        row.expires_at = data.expires_at
    else:
        db.add(
            HHToken(
                user_id=user.id,
                access_token=data.access_token,
                refresh_token=data.refresh_token,
                expires_at=data.expires_at,
            )
        )
    db.commit()
    return HHStatusOut(connected=True, expires_at=data.expires_at)


@router.get("/hh/status", response_model=HHStatusOut)
def hh_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(HHToken).filter(HHToken.user_id == user.id).first()
    if not row:
        return HHStatusOut(connected=False)
    if time.time() > row.expires_at:
        return HHStatusOut(connected=False, expires_at=row.expires_at)
    return HHStatusOut(connected=True, expires_at=row.expires_at)


@router.get("/hh/tokens")
def hh_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Токены HH текущего пользователя (для Streamlit-сессии)."""
    row = db.query(HHToken).filter(HHToken.user_id == user.id).first()
    if not row or time.time() > row.expires_at:
        raise HTTPException(status_code=404, detail="HH не подключён")
    return {
        "access_token": row.access_token,
        "refresh_token": row.refresh_token,
        "expires_at": row.expires_at,
    }


@router.delete("/hh")
def disconnect_hh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(HHToken).filter(HHToken.user_id == user.id).delete()
    db.commit()
    return {"ok": True}
