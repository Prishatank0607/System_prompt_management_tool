from pydantic import BaseModel, EmailStr, Field, ConfigDict, HttpUrl
from typing import Optional, List, Dict, Any, ForwardRef
from datetime import datetime
from enum import Enum

# Forward reference for User model
User = ForwardRef('User')

class TokenType(str, Enum):
    BEARER = "bearer"

class Token(BaseModel):
    """Authentication token response model"""
    access_token: str = Field(..., description="JWT access token for authentication")
    token_type: TokenType = Field(default=TokenType.BEARER, description="Type of the token")
    expires_in: int = Field(default=1800, description="Token expiration time in seconds")

class TokenData(BaseModel):
    """Token payload data model"""
    sub: str = Field(..., description="Subject (usually user email)")
    scopes: list[str] = Field(default_factory=list, description="List of scopes the token has access to")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")

class UserBase(BaseModel):
    """Base user model with common fields"""
    email: EmailStr = Field(..., description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name")

class UserCreate(UserBase):
    """Model for user registration"""
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")

class UserLogin(BaseModel):
    """Model for user login"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

class UserResponse(UserBase):
    """User response model (public data)"""
    id: int = Field(..., description="User ID")
    is_active: bool = Field(True, description="Whether the user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe",
            "is_active": True,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00"
        }
    })

class LoginResponse(Token, BaseModel):
    """Response model for successful login"""
    user: UserResponse = Field(..., description="Authenticated user details")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 1800,
            "user": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }
    })
