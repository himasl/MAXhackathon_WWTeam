import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/marshrut",
    )
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    scenario_data_dir: Path = Path(os.getenv("SCENARIO_DATA_DIR", "../data/scenarios"))
    dev_auth_enabled: bool = os.getenv("DEV_AUTH_ENABLED", "false").lower() == "true"
    dev_max_user_id: int = int(os.getenv("DEV_MAX_USER_ID", "123456"))


settings = Settings()
