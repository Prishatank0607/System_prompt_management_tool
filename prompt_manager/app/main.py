import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
# StaticFiles import removed - using Streamlit UI instead
from sqlalchemy.orm import Session
from typing import List, Optional
import time
import uvicorn

from . import models, __version__
from .core.config import settings
from .core.logger import get_logger
from .database import SessionLocal, engine, get_db
from .api.v1 import api as api_v1
from .api.v1 import errors

# Initialize logger
logger = get_logger(__name__)

# Create database tables
def create_tables():
    from .models.user import User  # Import User model to ensure it's registered
    models.Base.metadata.create_all(bind=engine)
    
# Initialize database tables
create_tables()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting Prompt Management Service...")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Database URL: {settings.DATABASE_URL}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Prompt Management Service...")

# Configure OpenAPI security scheme
security_scheme = {
    "OAuth2PasswordBearer": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter JWT Bearer token in the format: Bearer <token>"
    }
}

# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for managing and versioning AI prompts.",
    version=__version__,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Endpoints for user registration and login."
        },
        {
            "name": "Prompts",
            "description": "Endpoints for managing prompts. Requires authentication."
        }
    ],
    swagger_ui_parameters={
        "syntaxHighlight.theme": "obsidian",
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=__version__,
        description="API for managing and versioning AI prompts.",
        routes=app.routes,
        tags=[
            {
                "name": "Authentication",
                "description": "Endpoints for user registration and login."
            },
            {
                "name": "Prompts", 
                "description": "Endpoints for managing prompts. Requires authentication."
            }
        ]
    )
    
    # Define the security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token as: Bearer <token>"
        }
    }
    
    # Add security to all endpoints by default
    openapi_schema["security"] = [{"Bearer": []}]
    
    # Update paths to include security
    if "paths" in openapi_schema:
        for path in openapi_schema["paths"].values():
            for method in path.values():
                if "security" not in method:
                    method["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(
        f"Validation error for request: {request.method} {request.url}",
        extra={"errors": exc.errors()}
    )
    return await errors.http_error_handler(
        request,
        errors.PromptValidationError(
            "Invalid request data",
            details={"errors": exc.errors()}
        )
    )

# --- Router Inclusion ---

# Import routers
from .api.v1.endpoints.auth import router as auth_router
from .api.v1.api import router as prompts_router

# Public router for authentication
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])

# Protected router for prompts
app.include_router(
    prompts_router,
    prefix="/api/v1/prompts"
)

# Static files removed - using Streamlit UI instead

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all incoming requests and their responses."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (time.time() - start_time) * 1000
    process_time = round(process_time, 2)
    
    # Log response
    logger.info(
        f"Response: {request.method} {request.url} "
        f"Status: {response.status_code} "
        f"Time: {process_time}ms"
    )
    
    # Add headers
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Custom exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions and return a JSON response."""
    logger.error(
        f"Unhandled exception: {str(exc)}\n"
        f"Request: {request.method} {request.url}\n"
        f"Client: {request.client.host if request.client else 'unknown'}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred",
            "detail": str(exc),
            "status_code": 500
        }
    )

# Add custom exception handlers
app.add_exception_handler(errors.PromptError, errors.http_error_handler)


# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "prompt-management-service",
        "version": "1.0.0"
    }

# Root endpoint removed - use /docs for API documentation

# API info endpoint
@app.get("/api", status_code=status.HTTP_200_OK)
async def api_info() -> dict:
    """API information endpoint"""
    return {
        "service": "Prompt Management Service",
        "version": "1.0.0",
        "documentation": "/docs",
        "streamlit_ui": "http://localhost:8501",
        "description": "API for managing and versioning AI prompts"
    }

# Dependency override for testing (can be used in tests)
def override_get_db():
    """Override for testing"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For development with auto-reload
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )
