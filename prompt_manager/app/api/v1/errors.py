from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from typing import Any, Dict, Optional

class PromptError(Exception):
    """Base exception for prompt-related errors"""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, **kwargs):
        self.message = message
        self.status_code = status_code
        self.details = kwargs or {}
        super().__init__(message)

class PromptNotFoundError(PromptError):
    """Raised when a prompt is not found"""
    def __init__(self, message: str = "Prompt not found", **kwargs):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, **kwargs)

class PromptVersionExistsError(PromptError):
    """Raised when a prompt version already exists"""
    def __init__(self, message: str = "Prompt version already exists", **kwargs):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, **kwargs)

class PromptValidationError(PromptError):
    """Raised when prompt validation fails"""
    def __init__(self, message: str = "Invalid prompt data", **kwargs):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)

class TokenExpiredError(PromptError):
    """Raised when access token has expired"""
    def __init__(self, message: str = "Access token has expired. Please log in again.", **kwargs):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, **kwargs)

async def http_error_handler(request: Request, exc: PromptError) -> JSONResponse:
    """Convert custom exceptions to HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.message,
            "detail": exc.details.get("detail", exc.message),
            "status_code": exc.status_code,
            **exc.details
        }
    )
