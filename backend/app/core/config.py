import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


def normalize_database_url(url: str) -> str:
    """Accept plain ``postgres://`` URLs from hosting providers (Neon, Render).

    asyncpg does not understand ``sslmode``/``channel_binding`` query params, so they are
    translated to ``ssl=require`` or dropped.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable" and "ssl" not in query:
        query["ssl"] = "require"
    return urlunsplit(parts._replace(query=urlencode(query)))


def _test_tokens(raw: str) -> dict[str, int]:
    tokens: dict[str, int] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        token, _, max_user_id = item.rpartition(":")
        if token and max_user_id.isdigit():
            tokens[token] = int(max_user_id)
    return tokens


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@postgres:5432/marshrut",
        )
    )
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    # Render sets RENDER_EXTERNAL_URL automatically, so the webhook works even if
    # PUBLIC_URL was not filled in.
    public_url: str = (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    frontend_dist_dir: Path = Path(os.getenv("FRONTEND_DIST_DIR", "../frontend/dist"))
    scenario_data_dir: Path = Path(os.getenv("SCENARIO_DATA_DIR", "../data/scenarios"))

    dev_auth_enabled: bool = _bool("DEV_AUTH_ENABLED")
    dev_max_user_id: int = int(os.getenv("DEV_MAX_USER_ID", "123456"))
    secret_key: str = os.getenv("SECRET_KEY", "")
    access_token_ttl_seconds: int = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "604800"))
    init_data_max_age_seconds: int = int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "86400"))
    test_access_tokens: dict[str, int] = field(
        default_factory=lambda: _test_tokens(os.getenv("TEST_ACCESS_TOKENS", ""))
    )

    # MAX user ids of the team: they get «информация устарела» reports in the bot chat.
    support_max_user_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(item) for item in os.getenv("SUPPORT_MAX_USER_IDS", "").split(",") if item.strip().isdigit()
        )
    )
    # Commit of the running build: Render sets RENDER_GIT_COMMIT; shown in /health.
    version: str = (os.getenv("APP_VERSION") or os.getenv("RENDER_GIT_COMMIT") or "dev")[:12]
    max_bot_token: str = os.getenv("MAX_BOT_TOKEN", "")
    max_api_url: str = os.getenv("MAX_API_URL", "https://platform-api2.max.ru").rstrip("/")
    max_ca_bundle: str | None = os.getenv("MAX_CA_BUNDLE") or None
    # open_app: buttons open the Mini App registered for the bot (needs its URL set on
    # business.max.ru). link: buttons open PUBLIC_URL with a signed per-user login link.
    max_button_mode: str = os.getenv("MAX_BUTTON_MODE", "link").lower()
    link_token_ttl_seconds: int = int(os.getenv("LINK_TOKEN_TTL_SECONDS", "2592000"))
    max_bot_username: str = os.getenv("MAX_BOT_USERNAME", "").lstrip("@")
    bot_mode: str = os.getenv("BOT_MODE", "off").lower()
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    reminders_enabled: bool = _bool("REMINDERS_ENABLED", "true")
    reminder_interval_seconds: int = int(os.getenv("REMINDER_INTERVAL_SECONDS", "3600"))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def signing_key(self) -> str:
        # In development fall back to a fixed key so local runs work without setup.
        if self.secret_key:
            return self.secret_key
        if self.is_production:
            return ""
        return "development-only-secret"

    @property
    def max_webhook_secret(self) -> str:
        """Webhook secret in the alphabet MAX accepts ([A-Za-z0-9_-], 5-256 chars).

        Generated values (e.g. Render's base64) may contain ``/+=``; such values are mapped
        deterministically to their SHA-256 hex digest, used both for registration and for
        checking the ``X-Max-Bot-Api-Secret`` header.
        """
        raw = self.webhook_secret
        if not raw or re.fullmatch(r"[A-Za-z0-9_-]{5,256}", raw):
            return raw
        return hashlib.sha256(raw.encode()).hexdigest()

    @property
    def regions_file(self) -> Path:
        custom = os.getenv("REGIONS_FILE")
        return Path(custom) if custom else self.scenario_data_dir.parent / "regions.json"

    @property
    def universities_file(self) -> Path:
        custom = os.getenv("UNIVERSITIES_FILE")
        return Path(custom) if custom else self.scenario_data_dir.parent / "universities.json"

    @property
    def regional_services_file(self) -> Path:
        custom = os.getenv("REGIONAL_SERVICES_FILE")
        return (
            Path(custom) if custom else self.scenario_data_dir.parent / "regional_services.json"
        )

    @property
    def help_file(self) -> Path:
        custom = os.getenv("HELP_FILE")
        return Path(custom) if custom else self.scenario_data_dir.parent / "help.json"

    @property
    def mini_app_url(self) -> str:
        return self.public_url or self.frontend_url


settings = Settings()
