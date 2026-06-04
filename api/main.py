from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.database import Base, engine
from api.routers import auth, hh, history, resumes


def _ensure_columns():
    """create_all не добавляет колонки в существующие таблицы."""
    stmts = (
        "ALTER TABLE vacancy_analyses ADD COLUMN IF NOT EXISTS resume_adapted TEXT",
        "ALTER TABLE vacancy_analyses ADD COLUMN IF NOT EXISTS resume_original TEXT",
        "ALTER TABLE vacancy_analyses ADD COLUMN IF NOT EXISTS vacancy_url VARCHAR(500)",
    )
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    yield


app = FastAPI(title="Career Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(history.router)
app.include_router(hh.router)


@app.get("/health")
def health():
    return {"status": "ok"}
