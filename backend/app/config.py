from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./circa.db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    odds_api_key: str = ""
    odds_fetch_interval_minutes: int = 60
    current_season: int = 2025

    class Config:
        env_file = ".env"


settings = Settings()
