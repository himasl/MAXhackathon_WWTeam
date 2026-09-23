import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.errors import add_exception_handlers, error_response
from app.api.v1.router import router as api_v1_router
from app.bot.runtime import WEBHOOK_PATH, BotRuntime
from app.core.config import settings
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
)
app.include_router(api_v1_router)
add_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, str]:
    """Liveness. ``bot`` shows how the MAX bot is connected: off, polling, webhook, webhook_failed."""
    runtime: BotRuntime = request.app.state.bot
    return {"status": "ok", "bot": runtime.status}


@app.post(WEBHOOK_PATH, include_in_schema=False)
async def max_webhook(
    request: Request,
    background: BackgroundTasks,
    x_max_bot_api_secret: Annotated[str | None, Header()] = None,
) -> Response:
    if settings.webhook_secret and not hmac.compare_digest(
        x_max_bot_api_secret or "", settings.webhook_secret
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
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


mount_frontend(app, settings.frontend_dist_dir)
