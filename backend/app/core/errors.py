from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger("errors")


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None,
                 details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class InvalidTransition(AppError):
    status_code = 409
    code = "INVALID_TRANSITION"


def _envelope(request: Request, status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details,
                           "request_id": getattr(request.state, "request_id", None)}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _envelope(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return _envelope(request, 422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error", path=request.url.path,
                      request_id=getattr(request.state, "request_id", None))
        return _envelope(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")
