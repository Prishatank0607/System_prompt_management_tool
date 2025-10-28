"""
API v1 package for the Prompt Management Service.

This package contains all the API routes and endpoints for version 1 of the API.
"""

from fastapi import APIRouter

# Import all route modules
from . import errors, deps

# Import API routers
from .api import router as api_router
from .set_active_version import router as set_active_version_router

# Create the main API router
router = APIRouter(prefix="/api/v1")

# Include all routers
router.include_router(api_router)
router.include_router(set_active_version_router)

# This makes the router available when importing from ....api.v1
__all__ = ["router", "errors", "deps"]
