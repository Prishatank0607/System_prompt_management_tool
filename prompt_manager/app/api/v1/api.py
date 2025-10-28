from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import json
import time
from fastapi.responses import JSONResponse
from datetime import datetime
import time
import asyncio

from ...database import get_db
from ...core.security import get_current_active_user
from ...core.config import settings
from ...crud import crud
from ... import models
from ... import schemas
from .deps import get_db, get_prompt, get_prompt_version
from . import errors
# Auth endpoints removed to avoid duplication - handled in main.py

# Initialize logger
logger = logging.getLogger(__name__)

# Create API router with common parameters
router = APIRouter(
    prefix="",
    tags=["Prompts"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
        status.HTTP_403_FORBIDDEN: {"description": "Not enough permissions"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
    },
)

# Auth endpoints are handled separately in main.py to avoid duplication


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
        metadata_=prompt.metadata_ or {}
    )


# ======================
# Search and List Endpoints
# ======================

# Removed redundant /search endpoint - functionality consolidated into GET /

@router.post(
    "/",
    response_model=schemas.PromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new prompt version",
    response_description="The created prompt",
    responses={
        201: {"description": "Successfully created prompt"},
        400: {"description": "Invalid input data"},
        409: {"description": "Prompt version already exists"},
        500: {"description": "Internal server error"}
    }
)
async def create_prompt(
    *,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    prompt_in: schemas.PromptCreate = Body(..., 
        example={
            "name": "customer_support",
            "version": "1.0.0",
            "content": "You are a helpful customer support assistant...",
            "description": "Initial version of customer support prompt",
            "tags": ["support", "customer-service"],
            "metadata": {"category": "support", "priority": "high"}
        }
    ),
) -> schemas.PromptResponse:
    """
    Create a new prompt version.
    
    - **name**: Unique name for the prompt (e.g., 'customer_support')
    - **version**: Semantic version string (e.g., '1.0.0')
    - **content**: The actual prompt content
    - **created_by**: Email or identifier of the creator
    - **description**: Optional description of the prompt
    - **tags**: Optional list of tags for categorization
    - **metadata**: Optional JSON metadata
    """
    logger.info(f"Creating new prompt: {prompt_in.name} version {prompt_in.version}")
    
    try:
        prompt = crud.create_prompt(db=db, prompt=prompt_in, created_by=current_user.email)
        logger.info(f"Successfully created prompt {prompt.name} v{prompt.version} (ID: {prompt.id})")
        return convert_prompt_to_response(prompt)
        
    except ValueError as e:
        if "already exists" in str(e):
            raise errors.PromptVersionExistsError(
                message="Prompt version already exists",
                detail={"error": str(e)}
            )
        raise errors.PromptValidationError(
            message="Invalid prompt data",
            detail={"error": str(e)}
        )
        
    except Exception as e:
        logger.error(f"Error creating prompt: {str(e)}", exc_info=True)
        raise errors.PromptError(
            message="Failed to create prompt",
            detail={"error": str(e) or "An unexpected error occurred"}
        )

@router.get(
    "/",
    response_model=schemas.PaginatedResponse[schemas.PromptResponse],
    summary="Search and list prompts with filtering",
    response_description="Paginated list of prompts matching the criteria",
    responses={
        200: {"description": "Successfully retrieved prompts"},
        500: {"description": "Internal server error"}
    }
)
async def search_prompts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    query: Optional[str] = Query(
        None, 
        description="Search query to filter prompts by name, content, or description"
    ),
    status: Optional[schemas.PromptStatus] = Query(
        None, 
        description="Filter by prompt status"
    ),
    tag: Optional[str] = Query(
        None, 
        description="Filter by tag (exact match required)"
    ),
    created_by: Optional[str] = Query(
        None, 
        description="Filter by creator's email or identifier"
    ),
) -> schemas.PaginatedResponse[schemas.PromptResponse]:
    """
    Search and list prompts with comprehensive filtering and pagination.
    
    - **query**: Search text in prompt name, content, or description
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 1000)
    - **status**: Filter by prompt status (draft, active, archived)
    - **tag**: Filter by tag (exact match required)
    - **created_by**: Filter by creator's email or identifier
    
    If no filters are provided, returns all prompts with pagination.
    """
    logger.info(f"Searching prompts with filters: query={query}, status={status}, tag={tag}")
    
    try:
        prompts, total = crud.search_prompts(
            db=db,
            query=query or "",
            status=status,
            tag=tag,
            created_by=created_by,
            skip=skip,
            limit=limit
        )
        
        # Add X-Total-Count header for pagination
        response_headers = {"X-Total-Count": str(total)}
        
        logger.info(f"Found {len(prompts)} prompts out of {total} total")
        
        # Convert to response models
        items = [convert_prompt_to_response(prompt) for prompt in prompts]
        
        return schemas.PaginatedResponse[
            schemas.PromptResponse
        ](
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            page=skip // limit + 1,
            size=len(items),
            pages=(total + limit - 1) // limit
        )
        
    except Exception as e:
        logger.error(f"Error searching prompts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching prompts"
        ) from e

@router.get(
    "/{prompt_id}",
    response_model=schemas.PromptResponse,
    summary="Get a prompt by ID",
    response_description="The requested prompt",
    responses={
        200: {"description": "Successfully retrieved prompt"},
        404: {"description": "Prompt not found"},
        500: {"description": "Internal server error"}
    }
)
async def read_prompt(
    prompt_id: int = Path(..., description="The ID of the prompt to retrieve"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Retrieve a specific prompt by its unique identifier.
    
    - **prompt_id**: The unique identifier of the prompt to retrieve
    
    Returns the full prompt details including content, metadata, and version information.
    """
    logger.info(f"Retrieving prompt with ID: {prompt_id}")
    
    try:
        prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not prompt:
            logger.warning(f"Prompt with ID {prompt_id} not found")
            raise errors.PromptNotFoundError()
            
        logger.info(f"Successfully retrieved prompt {prompt.name} v{prompt.version} (ID: {prompt.id})")
        return convert_prompt_to_response(prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error retrieving prompt {prompt_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the prompt"
        ) from e

@router.get(
    "/name/{name}/version/{version}",
    response_model=schemas.PromptResponse,
    summary="Get a specific prompt version by name and version",
    response_description="The requested prompt version",
    responses={
        200: {"description": "Successfully retrieved prompt version"},
        404: {"description": "Prompt version not found"},
        500: {"description": "Internal server error"}
    }
)
async def read_prompt_by_name_version(
    name: str = Path(..., 
        description="The name of the prompt",
        example="customer_support"
    ),
    version: str = Path(
        ...,
        description="The version of the prompt to retrieve",
        example="1.0.0"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Retrieve a specific version of a prompt by its name and version.
    
    - **name**: The name of the prompt (e.g., 'customer_support')
    - **version**: The specific version to retrieve (e.g., '1.0.0')
    
    Returns the full prompt details for the specified version, including content,
    metadata, and status information.
    """
    logger.info(f"Retrieving prompt: {name} version {version}")
    
    try:
        # Get the specific prompt version
        prompt = crud.get_prompt_version(db, name=name, version=version)
        if not prompt:
            logger.warning(f"Prompt '{name}' version '{version}' not found")
            raise errors.PromptNotFoundError(
                detail=f"Prompt '{name}' with version '{version}' not found"
            )
        
        logger.info(f"Successfully retrieved prompt {prompt.name} v{prompt.version}")
        return convert_prompt_to_response(prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(
            f"Error retrieving prompt {name} v{version}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the prompt version"
        ) from e

@router.get(
    "/name/{name}/latest",
    response_model=schemas.PromptResponse,
    summary="Get the latest version of a prompt",
    response_description="The latest version of the requested prompt",
    responses={
        200: {"description": "Successfully retrieved the latest prompt version"},
        404: {"description": "No versions found for the specified prompt"},
        500: {"description": "Internal server error"}
    }
)
async def read_latest_prompt(
    name: str = Path(..., description="The name of the prompt"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Retrieve the most recent version of a prompt by its name.
    
    - **name**: The name of the prompt (e.g., 'customer_support')
    
    Returns the most recently created version of the specified prompt.
    """
    logger.info(f"Retrieving latest version of prompt: {name}")
    
    try:
        prompt = crud.get_latest_prompt(db=db, name=name)
        if not prompt:
            logger.warning(f"No versions found for prompt: {name}")
            raise errors.PromptNotFoundError(
                detail=f"No versions found for prompt '{name}'"
            )
            
        logger.info(f"Found latest version {prompt.version} for prompt: {name}")
        return convert_prompt_to_response(prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error retrieving latest version of {name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the latest prompt version"
        ) from e

@router.get(
    "/search/latest",
    response_model=schemas.PromptResponse,
    summary="Get latest prompt by tag, name, or metadata",
    response_description="The latest prompt matching the specified criteria",
    responses={
        200: {"description": "Successfully retrieved the latest prompt"},
        404: {"description": "No prompt found matching the criteria"},
        400: {"description": "Invalid search criteria"},
        500: {"description": "Internal server error"}
    }
)
async def get_latest_prompt_by_criteria(
    name: Optional[str] = Query(None, description="Filter by prompt name"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    metadata_key: Optional[str] = Query(None, description="Metadata key to search for"),
    metadata_value: Optional[str] = Query(None, description="Metadata value to match"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Get the latest prompt matching the specified criteria.
    
    - **name**: Filter by prompt name (partial match)
    - **tag**: Filter by tag (exact match)
    - **metadata_key**: Metadata key to search for
    - **metadata_value**: Metadata value to match (used with metadata_key)
    
    At least one filter criterion must be provided.
    Returns the most recently created prompt that matches the criteria.
    """
    logger.info(f"Getting latest prompt by criteria: name={name}, tag={tag}, metadata_key={metadata_key}, metadata_value={metadata_value}")
    
    # Validate that at least one criterion is provided
    if not any([name, tag, metadata_key]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search criterion must be provided (name, tag, or metadata_key)"
        )
    
    try:
        prompt = crud.get_latest_prompt_by_criteria(
            db=db,
            name=name,
            tag=tag,
            metadata_key=metadata_key,
            metadata_value=metadata_value
        )
        
        if not prompt:
            logger.warning(f"No prompt found matching criteria: name={name}, tag={tag}, metadata_key={metadata_key}")
            raise errors.PromptNotFoundError(
                detail="No prompt found matching the specified criteria"
            )
            
        logger.info(f"Found latest prompt: {prompt.name} v{prompt.version} (ID: {prompt.id})")
        return convert_prompt_to_response(prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error getting latest prompt by criteria: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the latest prompt"
        ) from e

@router.get(
    "/name/{name}/live",
    response_model=schemas.PromptResponse,
    summary="Get the live version of a prompt by name",
    response_description="The currently live version of the requested prompt",
    responses={
        200: {"description": "Successfully retrieved the live prompt version"},
        404: {
            "description": "No live version found for the specified prompt",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No live version found for prompt 'customer_support'"
                    }
                }
            }
        },
        500: {"description": "Internal server error"}
    }
)
async def read_live_prompt(
    name: str = Path(..., 
        description="The name of the prompt",
        example="customer_support"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Retrieve the currently live version of a prompt by its name.
    
    - **name**: The name of the prompt (e.g., 'customer_support')
    
    Returns the currently live version of the specified prompt, or 404 if no live version exists.
    """
    logger.info(f"Retrieving live version of prompt: {name}")
    
    try:
        prompt = crud.get_active_prompt(db=db, name=name)
        if not prompt:
            logger.warning(f"No live version found for prompt: {name}")
            raise errors.PromptNotFoundError(
                detail=f"No live version found for prompt '{name}'"
            )
            
        logger.info(f"Found live version {prompt.version} for prompt: {name}")
        return convert_prompt_to_response(prompt)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error retrieving live version of {name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the live prompt version"
        ) from e

@router.get(
    "/name/{name}/versions",
    response_model=List[schemas.PromptVersionInfo],
    summary="List all versions of a prompt",
    response_description="List of all versions for the specified prompt",
    responses={
        200: {
            "description": "Successfully retrieved prompt versions",
            "headers": {
                "X-Total-Count": {
                    "description": "Total number of versions available",
                    "schema": {"type": "integer"}
                }
            }
        },
        404: {"description": "No versions found for the specified prompt"},
        500: {"description": "Internal server error"}
    }
)
async def list_prompt_versions(
    name: str = Path(..., 
        description="The name of the prompt",
        example="customer_support"
    ),
    skip: int = Query(
        0, 
        ge=0, 
        description="Number of records to skip for pagination"
    ),
    limit: int = Query(
        100, 
        le=1000,
        description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> List[schemas.PromptVersionInfo]:
    """
    Retrieve a paginated list of all versions for a specific prompt.
    
    - **name**: The name of the prompt (e.g., 'customer_support')
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 1000)
    
    Returns a list of version information for the specified prompt,
    including version numbers, status, and creation details.
    """
    logger.info(f"Listing versions for prompt: {name}")
    
    try:
        # First check if any versions exist for this prompt
        prompt_exists = db.query(models.Prompt).filter(
            models.Prompt.name == name
        ).first()
        
        if not prompt_exists:
            logger.warning(f"No versions found for prompt: {name}")
            raise errors.PromptNotFoundError(
                detail=f"No versions found for prompt '{name}'"
            )
        
        # Get paginated versions
        prompts, total = crud.get_prompt_versions(
            db=db,
            name=name,
            skip=skip,
            limit=limit
        )
        
        logger.info(f"Found {len(prompts)} versions for prompt: {name}")
        
        # Convert to response models
        versions = [
            schemas.PromptVersionInfo(
                id=p.id,
                version=p.version,
                status=p.status,
                created_at=p.created_at,
                created_by=p.created_by,
                is_active=p.is_active,
                description=p.description,
                updated_at=p.updated_at
            )
            for p in prompts
        ]
        
        # Return response with X-Total-Count header
        return Response(
            content=json.dumps([v.dict() for v in versions], default=str),
            media_type="application/json",
            headers={"X-Total-Count": str(total)}
        )
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error listing versions for {name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving prompt versions"
        ) from e

@router.get(
    "/{prompt_id}/history",
    response_model=List[schemas.PromptHistoryItem],
    summary="Get change history for a prompt",
    response_description="List of all changes made to the specified prompt",
    responses={
        200: {
            "description": "Successfully retrieved prompt history",
            "headers": {
                "X-Total-Count": {
                    "description": "Total number of history items available",
                    "schema": {"type": "integer"}
                }
            }
        },
        404: {"description": "Prompt not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_prompt_history(
    prompt_id: int = Path(..., 
        description="The ID of the prompt",
        example=1
    ),
    skip: int = Query(
        0, 
        ge=0, 
        description="Number of records to skip for pagination"
    ),
    limit: int = Query(
        100, 
        le=1000,
        description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> List[schemas.PromptHistoryItem]:
    """
    Retrieve the complete change history for a specific prompt.
    
    - **prompt_id**: The ID of the prompt
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 1000)
    
    Returns an audit trail of all changes made to the prompt, including
    who made the change, when, and what was changed.
    """
    logger.info(f"Retrieving history for prompt ID: {prompt_id}")
    
    try:
        # Verify prompt exists
        prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not prompt:
            logger.warning(f"Prompt with ID {prompt_id} not found")
            raise errors.PromptNotFoundError(
                detail=f"Prompt with ID {prompt_id} not found"
            )
        
        # Get paginated history
        history, total = crud.get_prompt_history(
            db=db,
            prompt_id=prompt_id,
            skip=skip,
            limit=limit
        )
        
        logger.info(f"Found {len(history)} history items for prompt ID: {prompt_id}")
        
        # Convert to response format
        history_items = [
            schemas.PromptHistory(
                id=h.id,
                prompt_id=h.prompt_id,
                version=h.version,
                content=h.content,
                description=h.description,
                status=h.status,
                tags=h.tags or [],
                metadata_=h.metadata_ or {},
                changed_by=h.changed_by,
                changed_at=h.changed_at,
                change_reason=h.change_reason
            )
            for h in history
        ]
        
        # Return response with X-Total-Count header
        return Response(
            content=json.dumps([h.dict() for h in history_items], default=str),
            media_type="application/json",
            headers={"X-Total-Count": str(total)}
        )
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(f"Error retrieving history for prompt {prompt_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving prompt history"
        ) from e

@router.put(
    "/{prompt_id}",
    response_model=schemas.PromptResponse,
    summary="Update an existing prompt",
    response_description="The updated prompt",
    responses={
        200: {"description": "Successfully updated the prompt"},
        400: {"description": "Invalid input data"},
        403: {"description": "Not authorized to update this prompt"},
        404: {"description": "Prompt not found"},
        409: {"description": "Version conflict"},
        500: {"description": "Internal server error"}
    }
)
async def update_prompt(
    *,
    prompt_id: int = Path(..., 
        description="The ID of the prompt to update",
        example=1
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    prompt_in: schemas.PromptUpdate = Body(
        ...,
        example={
            "content": "Updated prompt content...",
            "description": "Updated description",
            "status": "active",
            "tags": ["updated", "prompt"],
            "metadata": {"updated_by": "user@example.com"}
        }
    )
) -> schemas.PromptResponse:
    """
    Update an existing prompt with new content or metadata.
    
    - **prompt_id**: The ID of the prompt to update
    - **content**: (Optional) New prompt content
    - **description**: (Optional) New description
    - **status**: (Optional) New status (draft, active, archived)
    - **tags**: (Optional) New list of tags
    - **metadata**: (Optional) New metadata dictionary
    - **updated_by**: Email or identifier of the user making the update
    
    Returns the updated prompt with its new values.
    """
    logger.info(f"Updating prompt ID {prompt_id} (updated by: {current_user.email})")
    
    try:
        # Get the existing prompt
        db_prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not db_prompt:
            logger.warning(f"Prompt with ID {prompt_id} not found for update")
            raise errors.PromptNotFoundError(
                detail=f"Prompt with ID {prompt_id} not found"
            )
        
        
        # Update the prompt
        logger.info(f"Applying updates to prompt ID {prompt_id}")
        updated_prompt = crud.update_prompt(
            db=db,
            db_prompt=db_prompt,
            prompt_update=prompt_in,
            updated_by=current_user.email
        )
        logger.info(f"Successfully updated prompt ID {prompt_id}")
        return convert_prompt_to_response(updated_prompt)
        
    except (errors.PromptError, errors.PromptVersionExistsError):
        raise  # Re-raise custom exceptions
        
    except Exception as e:
        logger.error(
            f"Error updating prompt {prompt_id}: {str(e)}", 
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the prompt"
        ) from e

@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prompt",
    response_description="No content - prompt successfully deleted",
    responses={
        204: {"description": "Prompt successfully deleted"},
        404: {"description": "Prompt not found"},
        403: {"description": "Not authorized to delete this prompt"},
        500: {"description": "Internal server error"}
    }
)
async def delete_prompt(
    *,
    prompt_id: int = Path(
        ...,
        description="The ID of the prompt to delete",
        example=1
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
        force: bool = Query(
        False,
        description="Force delete (permanent) instead of soft delete"
    )
) -> Response:
    """
    Delete a prompt, either via soft delete (default) or hard delete.
    
    - **prompt_id**: The ID of the prompt to delete
    - **deleted_by**: Email or identifier of the user performing the deletion
    - **force**: If true, permanently deletes the prompt; otherwise performs a soft delete (default: false)
    
    By default, this performs a soft delete (marks the prompt as deleted but keeps it in the database).
    Set `force=true` to permanently remove the prompt from the database.
    """
    logger.info(f"Deleting prompt ID {prompt_id} (deleted by: {current_user.email}, force: {force})")
    
    try:
        # Get the prompt to be deleted
        prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not prompt:
            logger.warning(f"Prompt with ID {prompt_id} not found for deletion")
            raise errors.PromptNotFoundError(
                detail=f"Prompt with ID {prompt_id} not found"
            )
        
        # Check if the prompt is referenced elsewhere (if implementing referential integrity)
        # This is a placeholder - implement based on your specific requirements
        if not force and crud.is_prompt_referenced(db, prompt_id):
            logger.warning(f"Cannot delete prompt {prompt_id}: it is referenced by other resources")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete prompt '{prompt.name}' (ID: {prompt_id}) as it is referenced by "
                    "other resources. Use force=true to override."
                )
            )
        
        # Perform the deletion
        if force:
            logger.info(f"Performing hard delete of prompt ID {prompt_id}")
            crud.hard_delete_prompt(db=db, db_prompt=prompt)
        else:
            logger.info(f"Performing soft delete of prompt ID {prompt_id}")
            crud.delete_prompt(db=db, db_prompt=prompt, deleted_by=current_user.email)
        
        logger.info(f"Successfully deleted prompt ID {prompt_id} (force={force})")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except errors.PromptError:
        raise  # Re-raise custom exceptions
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
        
    except Exception as e:
        logger.error(
            f"Error deleting prompt {prompt_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the prompt"
        ) from e


@router.post(
    "/name/{name}/version/{version}/activate",
    response_model=schemas.PromptResponse,
    summary="Set a specific prompt version as the live version",
    response_description="The live prompt version",
    responses={
        200: {"description": "Successfully set the prompt version as live"},
        400: {"description": "Invalid request or version conflict"},
        403: {"description": "Not authorized to modify this prompt"},
        404: {"description": "Prompt version not found"},
        500: {"description": "Internal server error"}
    }
)
async def set_active_version(
    name: str = Path(..., description="The name of the prompt"),
    version: str = Path(..., description="The version to set as live"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Set a specific version of a prompt as the live version.
    
    This will deactivate any currently live version of this prompt and
    set the specified version as live.
    """
    logger.info(f"Setting active version for prompt '{name}' to version {version} (user: {current_user.email})")
    
    try:
        # Get the prompt version to activate
        prompt = crud.get_prompt_version(db, name=name, version=version)
        if not prompt:
            logger.warning(f"Prompt '{name}' version '{version}' not found for activation")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt '{name}' version '{version}' not found"
            )
        
        # Check if the prompt is already the live version
        if prompt.is_active:
            logger.info(f"Prompt '{name}' version {version} is already the live version")
            return convert_prompt_to_response(prompt)
        
        # Set this version as the live version
        logger.info(f"Setting prompt '{name}' version {version} as live version")
        updated_prompt = crud.set_active_version(
            db=db,
            db_prompt=prompt,
            updated_by=current_user.email
        )
        
        logger.info(f"Successfully set prompt '{name}' version {version} as live version")
        return convert_prompt_to_response(updated_prompt)
        
    except Exception as e:
        logger.error(f"Error setting prompt '{name}' version {version} as live: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while setting the prompt version as live"
        ) from e


@router.post(
    "/{prompt_id}/create-version",
    response_model=schemas.PromptResponse,
    summary="Create a new version of an existing prompt",
    response_description="The newly created prompt version",
    responses={
        201: {"description": "Successfully created new prompt version"},
        400: {"description": "Invalid request or version already exists"},
        404: {"description": "Base prompt not found"},
        500: {"description": "Internal server error"}
    }
)
async def create_new_version(
    prompt_id: int = Path(..., description="ID of the base prompt"),
    version_data: schemas.PromptVersionCreate = Body(..., description="New version data"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Create a new version of an existing prompt.
    
    This creates a new prompt entry with the same name but different version,
    optionally with updated content, description, tags, and metadata.
    """
    logger.info(f"Creating new version for prompt ID {prompt_id} (user: {current_user.email})")
    
    try:
        # Get the base prompt
        base_prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not base_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt with ID {prompt_id} not found"
            )
        
        # Check if version already exists
        existing_version = crud.get_prompt_version(db, name=base_prompt.name, version=version_data.version)
        if existing_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Version '{version_data.version}' already exists for prompt '{base_prompt.name}'"
            )
        
        # Create new prompt version with base prompt data as defaults
        new_prompt_data = schemas.PromptCreate(
            name=base_prompt.name,
            version=version_data.version,
            content=version_data.content if version_data.content is not None else base_prompt.content,
            description=version_data.description if version_data.description is not None else base_prompt.description,
            tags=version_data.tags if version_data.tags is not None else (base_prompt.tags or []),
            metadata_=version_data.metadata_ if version_data.metadata_ is not None else (base_prompt.metadata_ or {})
        )
        
        # Create the new version
        new_prompt = crud.create_prompt(db, prompt=new_prompt_data, created_by=current_user.email)
        
        logger.info(f"Successfully created version '{version_data.version}' for prompt '{base_prompt.name}'")
        return convert_prompt_to_response(new_prompt)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating new version for prompt {prompt_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the new prompt version"
        ) from e


@router.post(
    "/{prompt_id}/update-version",
    response_model=schemas.PromptResponse,
    summary="Update prompt with auto-incremented version",
    response_description="The newly created prompt version with auto-incremented version number",
    responses={
        201: {"description": "Successfully created new version with updates"},
        404: {"description": "Base prompt not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_with_auto_version(
    prompt_id: int = Path(..., description="ID of the base prompt"),
    update_data: schemas.PromptUpdate = Body(..., description="Updated prompt data"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.PromptResponse:
    """
    Update a prompt by creating a new version with auto-incremented version number.
    
    This automatically increments the patch version (e.g., v1.0.0 → v1.0.1) and
    creates a new version with the updated content.
    """
    logger.info(f"Auto-updating prompt ID {prompt_id} (user: {current_user.email})")
    
    try:
        # Get the base prompt
        base_prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not base_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt with ID {prompt_id} not found"
            )
        
        # Get the latest version for this prompt name
        latest_version = crud.get_latest_prompt_version(db, name=base_prompt.name)
        if not latest_version:
            latest_version = base_prompt
        
        # Auto-increment version (patch version)
        current_version = latest_version.version
        version_parts = current_version.split('.')
        if len(version_parts) == 3:
            major, minor, patch = version_parts
            new_patch = str(int(patch) + 1)
            new_version = f"{major}.{minor}.{new_patch}"
        else:
            # Fallback if version format is unexpected
            new_version = f"{current_version}.1"
        
        # Create new prompt version with updated data
        new_prompt_data = schemas.PromptCreate(
            name=base_prompt.name,
            version=new_version,
            content=update_data.content if update_data.content is not None else latest_version.content,
            description=update_data.description if update_data.description is not None else latest_version.description,
            tags=update_data.tags if update_data.tags is not None else (latest_version.tags or []),
            metadata_=update_data.metadata_ if update_data.metadata_ is not None else (latest_version.metadata_ or {})
        )
        
        # Create the new version
        new_prompt = crud.create_prompt(db, prompt=new_prompt_data, created_by=current_user.email)
        
        logger.info(f"Successfully auto-incremented version to '{new_version}' for prompt '{base_prompt.name}'")
        return convert_prompt_to_response(new_prompt)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-updating prompt {prompt_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the prompt version"
        ) from e


@router.post(
    "/test-persona",
    summary="Test prompt with automatic persona selection",
    response_description="Generated response from the persona API",
    responses={
        200: {"description": "Successfully generated response"},
        404: {"description": "No active prompts found"},
        500: {"description": "Error calling persona API or finding relevant prompt"}
    }
)
async def test_persona_auto(
    user_input: str = Body(..., description="User input to test with the prompt"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Test a prompt by automatically selecting the most relevant active prompt
    based on the user's input and returning the generated response.
    
    This endpoint:
    1. Finds the most relevant active prompt based on the user's input
    2. Uses that prompt to generate a response
    3. Returns the response along with metadata about the prompt used
    """
    logger.info(f"Testing persona with automatic prompt selection (user: {current_user.email})")
    
    try:
        # Find the most relevant active prompt
        prompt_id = await crud.get_most_relevant_prompt_id(db, user_input)
        
        if not prompt_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No relevant active prompts found for the given input"
            )
        
        # Get the prompt details
        prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt with ID {prompt_id} not found"
            )
            
        # Call the existing test_persona_by_id endpoint with the found prompt_id
        response = await test_persona_by_id(
            prompt_id=prompt_id,
            user_input=user_input,
            db=db,
            current_user=current_user
        )
        
        # Format the response to match what the Streamlit UI expects
        if isinstance(response, dict) and 'data' in response:
            result = response['data']
            return {
                "success": True,
                "data": {
                    "prompt_id": prompt_id,
                    "prompt_used": {
                        "id": prompt.id,
                        "name": prompt.name,
                        "version": prompt.version,
                        "content": prompt.content[:200] + "..." if len(prompt.content) > 200 else prompt.content
                    },
                    "persona_type": result.get("persona_type", "dynamic_persona"),
                    "generated_response": result.get("generated_response", ""),
                    "metadata": {
                        "confidence_score": 1.0,  # Since we're using the most relevant prompt
                        "processing_time_ms": result.get("metadata", {}).get("processing_time_ms", 0),
                        "response_length": len(result.get("generated_response", "")),
                        **result.get("metadata", {})
                    }
                }
            }
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test_persona_auto: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding relevant prompt: {str(e)}"
        )

@router.post(
    "/{prompt_id}/test-persona",
    summary="Test a specific prompt with persona API",
    response_description="Generated response from the persona API",
    responses={
        200: {"description": "Successfully generated response"},
        404: {"description": "Prompt not found"},
        500: {"description": "Error calling persona API"}
    }
)
async def test_persona_by_id(
    prompt_id: int = Path(..., description="ID of the prompt to test"),
    user_input: str = Body(..., description="User input to test with the prompt"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Test a specific prompt by ID by calling its corresponding persona API.
    
    This is useful when you want to test a specific prompt rather than
    having the system automatically select one.
    """
    logger.info(f"Testing persona for prompt ID {prompt_id} (user: {current_user.email})")
    
    try:
        # Get the prompt
        prompt = crud.get_prompt(db, prompt_id=prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt with ID {prompt_id} not found"
            )
            
        # Verify the prompt is active
        if prompt.status != 'active' or not prompt.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompt with ID {prompt_id} is not active"
            )
        
        # Call GROQ API for real AI response
        start_time = time.time()
        
        try:
            from groq import Groq
            
            if not settings.GROQ_API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="GROQ API key not configured. Please set GROQ_API_KEY environment variable."
                )
            
            # Initialize GROQ client
            client = Groq(api_key=settings.GROQ_API_KEY)
            
            # Create the conversation with system prompt and user input
            messages = [
                {"role": "system", "content": prompt.content},
                {"role": "user", "content": user_input}
            ]
            
            # Call GROQ API with the same parameters as the test script
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract the response content safely
            if not completion.choices or not completion.choices[0].message:
                raise ValueError("No response content received from GROQ API")
                
            generated_response = completion.choices[0].message.content
            processing_time = int((time.time() - start_time) * 1000)
            
            # Extract persona type from prompt content or name (dynamic detection)
            persona_type = "dynamic_persona"
            if hasattr(prompt, 'metadata_') and prompt.metadata_ and "persona_type" in prompt.metadata_:
                persona_type = prompt.metadata_["persona_type"]
            elif hasattr(prompt, 'metadata') and isinstance(prompt.metadata, dict) and "persona_type" in prompt.metadata:
                persona_type = prompt.metadata["persona_type"]
            
            # Create response with real metadata
            response_data = {
                "prompt_info": {
                    "id": prompt.id,
                    "name": prompt.name,
                    "version": prompt.version,
                    "content": prompt.content[:200] + "..." if len(prompt.content) > 200 else prompt.content
                },
                "persona_type": persona_type,
                "user_input": user_input,
                "generated_response": generated_response,
                "metadata": {
                    "response_length": len(generated_response),
                    "processing_time_ms": processing_time,
                    "model_used": "llama-3.1-8b-instant",
                    "timestamp": datetime.utcnow().isoformat(),
                    "tokens_used": completion.usage.total_tokens if hasattr(completion, 'usage') and completion.usage else None
                }
            }
            
        except ImportError as e:
            error_msg = "GROQ library not installed. Please install: pip install groq"
            logger.error(f"{error_msg}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        except Exception as api_error:
            # Initialize error details
            error_detail = str(api_error)
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_type = type(api_error).__name__
            
            # Try to get more details if this is an HTTP error
            if hasattr(api_error, 'response'):
                try:
                    if hasattr(api_error.response, 'text'):
                        error_detail = api_error.response.text
                    if hasattr(api_error.response, 'status_code'):
                        status_code = api_error.response.status_code
                except Exception as e:
                    logger.error(f"Error extracting error details: {str(e)}")
            
            # Log detailed error information
            logger.error(f"GROQ API Error ({error_type}): {error_detail}")
            logger.error(f"Full error traceback: {traceback.format_exc()}")
            
            # Provide more user-friendly error messages
            if "401" in str(api_error) or "authentication" in str(api_error).lower():
                error_msg = "Authentication failed. Please check your GROQ API key."
            elif "429" in str(api_error):
                error_msg = "Rate limit exceeded. Please try again later."
            elif "404" in str(api_error):
                error_msg = "Model not found. Please check the model name."
            else:
                error_msg = f"Error calling GROQ API: {error_detail}"
            
            raise HTTPException(
                status_code=status_code,
                detail=error_msg
            )
        
        logger.info(f"Generated persona response for prompt '{prompt.name}' with persona type '{persona_type}'")
        
        return {
            "success": True,
            "data": response_data,
            "message": f"Successfully generated response using {persona_type} persona"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing persona for prompt {prompt_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while testing the persona"
        ) from e
