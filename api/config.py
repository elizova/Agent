from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg2://career:career@localhost:5432/career_agent"
    )
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    hh_client_id: str = ""
    hh_client_secret: str = ""
    hh_redirect_uri: str = "http://localhost:8501"


settings = Settings()
