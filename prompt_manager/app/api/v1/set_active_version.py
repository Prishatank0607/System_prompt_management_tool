from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from typing import Any, List, Optional, Dict
from sqlalchemy.orm import Session

from ... import models
from ... import schemas
from ...crud import crud
import logging
from .deps import get_db, get_prompt, get_prompt_version
from . import errors

# Initialize logger
logger = logging.getLogger(__name__)

# Create API router with common parameters
router = APIRouter(
    prefix="",
    tags=["prompts"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
        status.HTTP_403_FORBIDDEN: {"description": "Not enough permissions"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
    },
)

# Helper function to convert database model to response schema
def convert_prompt_to_response(prompt: models.Prompt) -> schemas.PromptResponse:
    """Convert a database Prompt model to a Pydantic response model."""
    return schemas.PromptResponse(
        id=prompt.id,
        name=prompt.name,
        version=prompt.version,
        content=prompt.content,
        description=prompt.description,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        created_by=prompt.created_by,
        status=prompt.status,
        is_active=prompt.is_active,
        tags=prompt.tags or [],
        metadata=prompt.metadata_ or {}
    )

@router.post(
    "/prompts/name/{name}/version/{version}/activate",
    response_model=schemas.PromptResponse,
    summary="Set a specific prompt version as active",
    response_description="The activated prompt version",
    responses={
        200: {"description": "Successfully activated the prompt version"},
        400: {"description": "Invalid request or version conflict"},
        403: {"description": "Not authorized to modify this prompt"},
        404: {"description": "Prompt version not found"},
        500: {"description": "Internal server error"}
    }
)
async def set_active_version(
    name: str = Path(..., 
        description="The name of the prompt",
        example="customer_support"
    ),
    version: str = Path(
        ...,
        description="The version to activate",
        example="1.2.0"
    ),
    db: Session = Depends(get_db),
    updated_by: str = Query(
        ...,
        description="Email or identifier of the user activating this version",
        example="admin@example.com"
    )
) -> schemas.PromptResponse:
    """
    Set a specific version of a prompt as the active version.
    
    - **name**: The name of the prompt
    - **version**: The version to activate
    - **updated_by**: Email or identifier of the user performing the action
    
    This will deactivate any currently active version of this prompt and
    activate the specified version.
    """
    logger.info(
        f"Setting active version for prompt '{name}' to version {version} "
        f"(updated by: {updated_by})"
    )
    
    try:
        # Get the prompt version to activate
        prompt = crud.get_prompt_version(db, name=name, version=version)
        if not prompt:
            logger.warning(f"Prompt '{name}' version '{version}' not found for activation")
            raise errors.PromptNotFoundError(
                detail=f"Prompt '{name}' version '{version}' not found"
            )
        
        # Check if the prompt is already active
        if prompt.is_active:
            logger.info(
                f"Prompt '{name}' version {version} is already active. "
                "No changes made."
            )
            return convert_prompt_to_response(prompt)
        
        # Set this version as active
        logger.info(f"Activating prompt '{name}' version {version}")
        updated_prompt = crud.set_active_version(
            db=db,
            db_prompt=prompt,
            updated_by=updated_by
        )
        
        logger.info(
            f"Successfully activated prompt '{name}' version {version}. "
            f"Previous active version deactivated."
        )
        
        return convert_prompt_to_response(updated_prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(
            f"Error activating prompt '{name}' version {version}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while activating the prompt version"
        ) from e
