import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/marshrut",
    )
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


settings = Settings()

