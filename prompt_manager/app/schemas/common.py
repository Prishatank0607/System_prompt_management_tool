from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int

class MessageResponse(BaseModel):
    """Standard message response model"""
    message: str
    
class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str
    code: Optional[str] = None
    
class StatusResponse(BaseModel):
    """Standard status response model"""
    status: str
    message: Optional[str] = None
