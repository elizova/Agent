from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    hh_token: Mapped["HHToken | None"] = relationship(back_populates="user", uselist=False)
    resumes: Mapped[list["SavedResume"]] = relationship(back_populates="user")
    search_sessions: Mapped[list["SearchSession"]] = relationship(back_populates="user")
    analyses: Mapped[list["VacancyAnalysis"]] = relationship(back_populates="user")


class HHToken(Base):
    __tablename__ = "hh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[float] = mapped_column()

    user: Mapped["User"] = relationship(back_populates="hh_token")


class SavedResume(Base):
    __tablename__ = "saved_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[str] = mapped_column(String(32))

    user: Mapped["User"] = relationship(back_populates="resumes")


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[str] = mapped_column(String(32))
    user_query: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[str | None] = mapped_column(Text)
    found_count: Mapped[int | None] = mapped_column(Integer)
    results_count: Mapped[int | None] = mapped_column(Integer)
    resume_preview: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="search_sessions")


class VacancyAnalysis(Base):
    __tablename__ = "vacancy_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[str] = mapped_column(String(32))
    vacancy_id: Mapped[str | None] = mapped_column(String(64))
    vacancy_title: Mapped[str | None] = mapped_column(String(500))
    vacancy_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(64))
    requirements_json: Mapped[str | None] = mapped_column(Text)
    comparison_json: Mapped[str | None] = mapped_column(Text)
    ats_before: Mapped[int | None] = mapped_column(Integer)
    ats_after: Mapped[int | None] = mapped_column(Integer)
    resume_original: Mapped[str | None] = mapped_column(Text)
    resume_adapted: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="analyses")
