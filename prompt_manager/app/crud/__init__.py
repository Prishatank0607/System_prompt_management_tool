"""
CRUD operations for the Prompt Management Service.

This module provides database operations following the Repository pattern.
"""
# Import models first to avoid circular imports
from .. import models

# Then import crud functions
from .crud import (
    create_prompt,
    get_prompt,
    get_prompt_version,
    get_latest_prompt,
    get_active_prompt,
    get_prompt_versions,
    update_prompt,
    delete_prompt,
    search_prompts,
    get_prompt_history,
    set_active_version,
)

__all__ = [
    "create_prompt",
    "get_prompt",
    "get_prompt_version",
    "get_latest_prompt",
    "get_active_prompt",
    "get_prompt_versions",
    "update_prompt",
    "delete_prompt",
    "search_prompts",
    "get_prompt_history",
    "set_active_version",
]
