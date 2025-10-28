from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from jose import JWTError, jwt
from pydantic import BaseModel

from ....core.config import settings
from ....core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user,
    oauth2_scheme
)
from .... import models
from .... import schemas
from ....database import get_db

# Create a router with the auth prefix
router = APIRouter()

class RegisterResponse(BaseModel):
    """Response model for user registration"""
    id: int
    email: str
    full_name: Optional[str] = None
    message: str = "User registered successfully"

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password",
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Email already registered"},
        422: {"description": "Validation error"}
    },
    response_description="User registration successful"
)
async def register_user(
    user: schemas.UserCreate, 
    db: Session = Depends(get_db)
) -> RegisterResponse:
    """
    Register a new user with the following information:
    - **email**: must be a valid email address
    - **password**: at least 6 characters
    - **full_name**: user's full name (optional)
    
    Returns the registered user's ID, email, and full name.
    """
    # Check if user already exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "message": "User registered successfully"
    }

@router.post(
    "/token",
    response_model=schemas.LoginResponse,
    summary="OAuth2 token login",
    description="Get an access token for API requests using email and password",
    response_description="Authentication token and user details",
    responses={
        200: {"description": "Successfully authenticated"},
        401: {"description": "Incorrect email or password"},
        422: {"description": "Validation error"}
    }
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> schemas.LoginResponse:
    """
    OAuth2 compatible token login, get an access token for future requests.
    
    - **username**: Your email address
    - **password**: Your password
    
    Returns an access token that should be included in the Authorization header
    for protected endpoints: `Authorization: Bearer <token>`
    """
    # Authenticate user
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with additional claims
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "email": user.email,
            "user_id": str(user.id),
            "scopes": ["me"]  # Add default scope for basic user access
        },
        expires_delta=access_token_expires
    )
    
    # Debug log the token creation
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Created access token for user: {user.email}")
    
    # Prepare user response
    user_response = schemas.UserResponse.model_validate(user)
    
    return schemas.LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds (24 hours)
        user=user_response
    )

# Login endpoint removed - use /token for OAuth2 compliance

@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Get current user",
    description="Get details of the currently authenticated user",
    responses={
        200: {"description": "Successfully retrieved user details"},
        401: {"description": "Not authenticated"}
    }
)
async def read_users_me(
    current_user: models.User = Depends(get_current_active_user),
    token: str = Depends(oauth2_scheme)
) -> schemas.UserResponse:
    """
    Get details of the currently authenticated user.
    
    Requires a valid access token in the Authorization header.
    """
    from fastapi import Request
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Current user: {current_user}")
    logger.info(f"Token: {token}")
    
    if not current_user:
        logger.error("No current user found")
    
    return schemas.UserResponse.model_validate(current_user)
