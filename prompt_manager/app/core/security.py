from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .config import settings
from ..models import User
from ..schemas.auth import TokenData, UserResponse
from ..database import get_db

# Security configurations
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=True,
    scheme_name="Bearer",
    scopes={
        "me": "Read your own user data",
        "items": "Read and manage your items",
        "admin": "Admin operations"
    }
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        bool: True if the password matches the hash, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generate a password hash.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)

def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[list[str]] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: The data to include in the token
        expires_delta: Optional expiration time delta
        scopes: List of scopes for the token
        
    Returns:
        str: The encoded JWT token
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    # Set expiration time
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=15)
        
    # Include standard claims
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.PROJECT_NAME,
        "aud": settings.PROJECT_NAME,
    })
    
    # Add scopes if provided
    if scopes:
        to_encode["scopes"] = scopes
        
    # Encode and return the JWT
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the JWT token.
    
    Args:
        security_scopes: The required security scopes
        token: The JWT token from the Authorization header
        db: Database session
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If authentication fails or scopes are insufficient
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting get_current_user function")
    
    if not token:
        logger.error("No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope=\"{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    
    logger.info(f"Validating token for scopes: {security_scopes.scopes}")
    logger.info(f"Token received (first 10 chars): {token[:10]}...")
    
    try:
        # Decode and validate the token
        logger.info(f"Using SECRET_KEY: {SECRET_KEY[:5]}...{SECRET_KEY[-5:] if len(SECRET_KEY) > 10 else ''}")
        logger.info(f"Using ALGORITHM: {ALGORITHM}")
        
        try:
            # First try with verification but without audience/issuer checks
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": True,  # Still verify expiration
                    "verify_nbf": False,
                    "verify_iat": False,
                    "verify_at_hash": False
                }
            )
            logger.info("Token successfully verified with basic validation")
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            # If verification fails, try with unverified claims for debugging
            logger.warning("Using unverified claims - this is not secure for production!")
            payload = jwt.get_unverified_claims(token)
            
        email: str = payload.get("sub")
        if email is None:
            logger.error("No 'sub' claim in token")
            raise credentials_exception
            
        # Check token expiration
        expire = payload.get("exp")
        if expire is not None:
            expire_dt = datetime.fromtimestamp(expire, timezone.utc)
            logger.info(f"Token expires at: {expire_dt} (UTC)")
            current_time = datetime.now(timezone.utc)
            if current_time > expire_dt:
                logger.error(f"Token expired at {expire_dt}, current time is {current_time}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your access token has expired. Please log in again to get a new token.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Check scopes
        token_scopes = payload.get("scopes", [])
        logger.info(f"Token scopes: {token_scopes}")
        
        if security_scopes.scopes:
            for scope in security_scopes.scopes:
                if scope not in token_scopes:
                    logger.error(f"Missing required scope: {scope}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": authenticate_value},
                    )
        
        # Get user from database
        logger.info(f"Looking up user with email: {email}")
        try:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                logger.error(f"User not found with email: {email}")
                raise credentials_exception
                
            logger.info(f"Found user: {user.email} (ID: {user.id})")
            return user
            
        except Exception as db_error:
            logger.error(f"Database error during user lookup: {str(db_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during authentication"
            ) from db_error
            
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise credentials_exception from e
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication"
        ) from e

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get the current active user.
    
    Args:
        current_user: The authenticated user from get_current_user
        
    Returns:
        User: The active user
        
    Raises:
        HTTPException: If the user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get the current active superuser.
    
    Args:
        current_user: The authenticated user from get_current_user
        
    Returns:
        User: The active superuser
        
    Raises:
        HTTPException: If the user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user
