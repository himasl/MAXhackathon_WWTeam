import asyncio
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)
# Keeps references to fire-and-forget alert tasks until they finish.
_ALERT_TASKS: set[asyncio.Task[bool]] = set()


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def application_error_handler(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApplicationError)
    return error_response(error.status_code, error.code, error.message)


async def validation_error_handler(_: Request, __: Exception) -> JSONResponse:
    assert isinstance(__, RequestValidationError)
    return error_response(422, "VALIDATION_ERROR", "Request validation failed")


async def http_error_handler(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)
    code = "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
    return error_response(error.status_code, code, str(error.detail))


async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.exception(
        "Unhandled error on %s %s [request_id=%s]", request.method, request.url.path, request_id
    )
    # The id lets support find this exact failure in the logs from a user's screenshot.
    response = error_response(
        500, "INTERNAL_ERROR", f"Internal server error (request_id: {request_id})"
    )
    response.headers["X-Request-ID"] = request_id
    runtime = getattr(request.app.state, "bot", None)
    if runtime is not None:
        text = (
            f"⚠️ Ошибка 500: {request.method} {request.url.path}\n"
            f"{type(error).__name__}: {str(error)[:200]}\n"
            f"Код для поддержки: {request_id} — ищите его в логах Render."
        )
        task = asyncio.create_task(runtime.alert_team(text))
        _ALERT_TASKS.add(task)
        task.add_done_callback(_ALERT_TASKS.discard)
    return response


def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
