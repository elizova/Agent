from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None

    class Config:
        from_attributes = True


class HHTokenIn(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: float


class HHStatusOut(BaseModel):
    connected: bool
    expires_at: float | None = None


class ResumeIn(BaseModel):
    name: str
    body: str


class ResumeOut(BaseModel):
    id: int
    name: str
    body: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True


class SearchSaveIn(BaseModel):
    user_query: str
    params: dict
    found_count: int
    results_count: int
    resume_preview: str = ""


class AnalysisSaveIn(BaseModel):
    vacancy_id: str
    vacancy_title: str
    source: str
    requirements: dict
    comparison: dict
    ats_before: int
    ats_after: int | None
    resume_original: str
    resume_adapted: str = ""
    vacancy_url: str = ""


class AnalysisResumePatchIn(BaseModel):
    resume_adapted: str = Field(min_length=1, max_length=8000)
