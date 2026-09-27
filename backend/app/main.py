import hmac
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.errors import add_exception_handlers, error_response
from app.api.v1.router import router as api_v1_router
from app.assistant.service import assistant_mode
from app.bot.runtime import WEBHOOK_PATH, BotRuntime
from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime: BotRuntime = app.state.bot
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(
    title="Маршрут API",
    version="1.0.0",
    description=(
        "API сервиса «Маршрут»: персональный маршрут действий для студента после переезда "
        "в другой регион. Сервис не является государственным и не принимает юридически "
        "значимых решений."
    ),
    lifespan=lifespan,
)
# Created eagerly so the app works (with notifications disabled) even without lifespan.
app.state.bot = BotRuntime(settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Response:
    """Tag every request with an id: logged on errors and returned in X-Request-ID."""
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", incoming) else uuid4().hex[:12]
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_v1_router)
add_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, str]:
    """Liveness for monitoring and reviewers.

    ``bot``: how the MAX bot is connected (off, polling, webhook, webhook_failed);
    ``database``: ok / unavailable; ``assistant``: rag (RAG_URL set) or stub; ``version``: commit of the running build, to check it
    matches the submitted commit hash.
    """
    runtime: BotRuntime = request.app.state.bot
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - reported, not raised: liveness must answer
        logger.warning("Database is unavailable for /health")
        database = "unavailable"
    return {
        "status": "ok",
        "bot": runtime.status,
        "database": database,
        "version": settings.version,
        "assistant": assistant_mode(),
    }


@app.post(WEBHOOK_PATH, include_in_schema=False)
async def max_webhook(
    request: Request,
    background: BackgroundTasks,
    x_max_bot_api_secret: Annotated[str | None, Header()] = None,
) -> Response:
    if settings.is_production and not settings.max_webhook_secret:
        # Without a secret anyone could post fake updates: in production require one.
        return error_response(401, "UNAUTHORIZED", "WEBHOOK_SECRET is not configured")
    if settings.max_webhook_secret and not hmac.compare_digest(
        x_max_bot_api_secret or "", settings.max_webhook_secret
    ):
        return error_response(401, "UNAUTHORIZED", "Invalid webhook secret")
    try:
        update: Any = await request.json()
    except ValueError:
        return error_response(422, "VALIDATION_ERROR", "Request validation failed")
    if isinstance(update, dict):
        runtime: BotRuntime = request.app.state.bot
        # Answer MAX immediately; the update is processed after the response.
        background.add_task(runtime.safe_handle, update)
    return JSONResponse({"ok": True})


def mount_frontend(application: FastAPI, dist: Path) -> None:
    """Serve the built Mini App from the same origin as the API (one HTTPS URL)."""
    index = dist / "index.html"
    if not index.is_file():
        logger.info("Frontend build not found at %s, static serving disabled", dist)
        return
    if (dist / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @application.get("/", include_in_schema=False)
    @application.get("/{path:path}", include_in_schema=False)
    async def spa(path: str = "") -> Response:
        if path.startswith(("api/", "max/")) or path in {"docs", "redoc", "openapi.json"}:
            return error_response(404, "NOT_FOUND", "Not Found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            # The service worker must be re-checked on every visit to pick up new versions.
            headers = {"Cache-Control": "no-cache"} if path == "sw.js" else None
            return FileResponse(candidate, headers=headers)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


mount_frontend(app, settings.frontend_dist_dir)
