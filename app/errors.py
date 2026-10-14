"""Standardized error classes and global exception handlers.

All errors consistently return JSON payload:
{
    "detail": "Error message description",
    "code": "ERROR_CODE"
}
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base application exception with HTTP status code and machine-readable error code."""

    def __init__(
        self,
        detail: str,
        code: str = "ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad Request", code: str = "BAD_REQUEST"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_400_BAD_REQUEST)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Unauthorized", code: str = "UNAUTHORIZED"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Forbidden", code: str = "FORBIDDEN"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_403_FORBIDDEN)


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(AppException):
    def __init__(self, detail: str = "Conflict", code: str = "CONFLICT"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_409_CONFLICT)


class LockedException(AppException):
    def __init__(self, detail: str = "Account temporarily locked due to repeated failed attempts", code: str = "ACCOUNT_LOCKED"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_423_LOCKED)


class RateLimitException(AppException):
    def __init__(self, detail: str = "Request limit reached (maximum 3 requests per journey)", code: str = "LIMIT_EXCEEDED"):
        super().__init__(detail=detail, code=code, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard Starlette / FastAPI HTTPExceptions."""
    code_mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        423: "LOCKED",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_mapping.get(exc.status_code, "HTTP_ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": code},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic request validation errors."""
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "Invalid request payload")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    detail = f"{loc}: {msg}" if loc else msg
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail, "code": "VALIDATION_ERROR"},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled unexpected exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later.", "code": "INTERNAL_SERVER_ERROR"},
    )
