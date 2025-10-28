"""
Schemas package containing all Pydantic models for the application.
"""

# Common schemas
from .common import (
    PaginatedResponse,
    MessageResponse,
    ErrorResponse,
    StatusResponse
)

# Auth schemas
from .auth import (
    UserBase,
    UserCreate,
    UserResponse,
    Token,
    TokenData,
    LoginResponse,
    UserLogin
)

# Prompt schemas
from .prompt import (
    PromptStatus,
    PromptBase,
    PromptCreate,
    PromptUpdate,
    PromptInDB,
    PromptResponse,
    Prompt,
    PromptHistoryBase,
    PromptHistoryCreate,
    PromptHistoryInDB,
    PromptHistory,
    PromptVersionInfo,
    PromptVersionCreate
)

from .prompt_history_item import PromptHistoryItem

__all__ = [
    # Common schemas
    "PaginatedResponse",
    "MessageResponse",
    "ErrorResponse",
    "StatusResponse",
    
    # Auth schemas
    "UserBase",
    "UserCreate",
    "UserInDB",
    "User",
    "Token",
    "TokenData",
    "UserLogin",
    
    # Prompt schemas
    "PromptStatus",
    "PromptBase",
    "PromptCreate",
    "PromptUpdate",
    "PromptInDB",
    "PromptResponse",
    "Prompt",
    "PromptHistoryBase",
    "PromptHistoryCreate",
    "PromptHistoryInDB",
    "PromptHistory",
    "PromptVersionInfo",
    "PromptVersionCreate",
    "PromptHistoryItem"
]
