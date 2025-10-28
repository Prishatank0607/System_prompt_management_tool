from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import SessionLocal
from ... import models
from ...crud import crud

def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session.
    
    Yields:
        Session: A database session
        
    Ensures:
        The session is closed after the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_prompt(
    prompt_id: int, 
    db: Session = Depends(get_db)
) -> models.Prompt:
    """Get a prompt by ID or raise a 404 if not found.
    
    Args:
        prompt_id: The ID of the prompt to retrieve
        db: Database session
        
    Returns:
        models.Prompt: The requested prompt
        
    Raises:
        HTTPException: If the prompt is not found (404)
    """
    prompt = crud.get_prompt(db, prompt_id=prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    return prompt

def get_prompt_version(
    name: str,
    version: str,
    db: Session = Depends(get_db)
) -> models.Prompt:
    """Get a specific prompt version or raise a 404 if not found.
    
    Args:
        name: The name of the prompt
        version: The version of the prompt to retrieve
        db: Database session
        
    Returns:
        models.Prompt: The requested prompt version
        
    Raises:
        HTTPException: If the prompt version is not found (404)
    """
    prompt = crud.get_prompt_version(db, name=name, version=version)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' with version '{version}' not found"
        )
    return prompt
