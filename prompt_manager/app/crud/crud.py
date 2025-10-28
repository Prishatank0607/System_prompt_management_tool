from sqlalchemy import or_, and_, func, text
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime
import logging
import os
from groq import Groq
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from ..core.config import settings

# Initialize logger
logger = logging.getLogger(__name__)

# Use absolute imports to avoid circular imports
from .. import models, schemas
from ..models import Prompt, PromptHistory, PromptStatus

# Helper functions
def _log_prompt_change(
    db: Session,
    prompt_id: int,
    version: str,
    changed_by: str,
    action: str,
    changes: Optional[Dict[str, Any]] = None
) -> None:
    """Log changes to prompt in the history table"""
    # Get the current prompt to log its state
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        logger.warning(f"Prompt with ID {prompt_id} not found for history logging")
        return
        
    history = PromptHistory(
        prompt_id=prompt_id,
        version=version,
        content=prompt.content,
        description=prompt.description,
        status=prompt.status,
        tags=prompt.tags,
        metadata_=prompt.metadata_,
        changed_by=changed_by,
        change_reason=f"{action}: {changes}" if changes else action
    )
    db.add(history)
    db.commit()

def _deactivate_other_versions(db: Session, prompt_name: str, exclude_id: int) -> None:
    """Deactivate all other versions when a new version is set as live"""
    updated_count = db.query(Prompt).filter(
        Prompt.name == prompt_name,
        Prompt.id != exclude_id
    ).update({Prompt.is_active: False})
    db.commit()
    logger.info(f"Deactivated {updated_count} other versions for prompt '{prompt_name}'")

# CRUD Operations
def create_prompt(db: Session, prompt: schemas.PromptCreate, created_by: str) -> Prompt:
    """
    Create a new prompt version with automatic status management
    
    Args:
        db: Database session
        prompt: Prompt creation data
        created_by: Email or identifier of the user creating the prompt
    
    Returns:
        The created prompt
    """
    # Check if this exact name/version combination already exists
    existing = get_prompt_version(db, name=prompt.name, version=prompt.version)
    if existing:
        raise ValueError(
            f"A prompt with name '{prompt.name}' and version '{prompt.version}' already exists. "
            f"Please choose a different version number or update the existing prompt."
        )
    
    # All new prompts start as draft - no need to check for active status conflicts during creation
    
    # Create new prompt with automatic status management
    db_prompt = Prompt(
        name=prompt.name,
        version=prompt.version,
        content=prompt.content,
        description=prompt.description,
        status=PromptStatus.DRAFT,  # Always start as draft
        is_active=False,  # Never active on creation
        tags=prompt.tags,
        metadata_=prompt.metadata_,
        created_by=created_by
    )
    
    db.add(db_prompt)
    
    try:
        db.flush()  # This will trigger any database constraints
        
        # All prompts start as draft - no activation logic needed during creation
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        if "UNIQUE constraint failed" in str(e) and "prompts.name, prompts.version" in str(e):
            raise ValueError(
                f"A prompt with name '{prompt.name}' and version '{prompt.version}' already exists. "
                f"Please choose a different version number or update the existing prompt."
            )
        logger.error(f"Database error in create_prompt: {str(e)}", exc_info=True)
        raise ValueError("Failed to create prompt due to a database error. Please try again.")
    
    # Log the creation
    _log_prompt_change(
        db=db,
        prompt_id=db_prompt.id,
        version=db_prompt.version,
        changed_by=created_by,
        action="create",
        changes={"status": "draft"}
    )
    
    return db_prompt

def get_prompt(db: Session, prompt_id: int) -> Optional[Prompt]:
    """Get a prompt by ID"""
    return db.query(Prompt).filter(Prompt.id == prompt_id).first()

def get_prompt_version(db: Session, name: str, version: str) -> Optional[Prompt]:
    """Get a specific version of a prompt"""
    return db.query(Prompt).filter(
        Prompt.name == name,
        Prompt.version == version
    ).first()

def get_latest_prompt(db: Session, name: str) -> Optional[Prompt]:
    """Get the latest version of a prompt by name"""
    return db.query(Prompt).filter(
        Prompt.name == name
    ).order_by(Prompt.created_at.desc()).first()

def get_latest_prompt_version(db: Session, name: str) -> Optional[Prompt]:
    """Get the latest version of a prompt by name (ordered by version number)"""
    return db.query(Prompt).filter(
        Prompt.name == name
    ).order_by(Prompt.version.desc()).first()

def get_latest_prompt_by_criteria(
    db: Session,
    name: Optional[str] = None,
    tag: Optional[str] = None,
    metadata_key: Optional[str] = None,
    metadata_value: Optional[str] = None
) -> Optional[Prompt]:
    """Get the latest prompt matching the specified criteria"""
    query = db.query(Prompt)
    
    # Apply filters based on provided criteria
    if name:
        query = query.filter(Prompt.name.ilike(f"%{name}%"))
    
    if tag:
        # Check if the tag exists in the tags JSON array (SQLite compatible)
        from sqlalchemy import func
        query = query.filter(func.json_extract(Prompt.tags, '$').like(f'%"{tag}"%'))
    
    if metadata_key:
        if metadata_value:
            # Check for specific key-value pair in metadata (SQLite compatible)
            from sqlalchemy import func
            query = query.filter(func.json_extract(Prompt.metadata_, f'$.{metadata_key}') == metadata_value)
        else:
            # Check if the key exists in metadata (SQLite compatible)
            from sqlalchemy import func
            query = query.filter(func.json_extract(Prompt.metadata_, f'$.{metadata_key}').isnot(None))
    
    # Order by creation date descending to get the latest
    return query.order_by(Prompt.created_at.desc()).first()

def get_active_prompt(db: Session, name: str) -> Optional[Prompt]:
    """Get the active version of a prompt"""
    return db.query(Prompt).filter(
        Prompt.name == name,
        Prompt.is_active == True
    ).first()

def get_prompt_versions(
    db: Session, 
    name: str,
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[Prompt], int]:
    """
    Get all versions of a prompt with pagination
    Returns: (list_of_prompts, total_count)
    """
    query = db.query(Prompt).filter(Prompt.name == name)
    total = query.count()
    
    prompts = query.order_by(
        Prompt.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return prompts, total

def update_prompt(
    db: Session, 
    db_prompt: Prompt, 
    prompt_update: schemas.PromptUpdate,
    updated_by: str
) -> Prompt:
    """Update an existing prompt"""
    changes = {}
    
    # Track changes
    if prompt_update.content is not None and prompt_update.content != db_prompt.content:
        changes["content"] = {"old": db_prompt.content, "new": prompt_update.content}
        db_prompt.content = prompt_update.content
    
    if prompt_update.description is not None and prompt_update.description != db_prompt.description:
        changes["description"] = {"old": db_prompt.description, "new": prompt_update.description}
        db_prompt.description = prompt_update.description
    
    if prompt_update.tags is not None and set(prompt_update.tags or []) != set(db_prompt.tags or []):
        changes["tags"] = {"old": db_prompt.tags, "new": prompt_update.tags}
        db_prompt.tags = prompt_update.tags
    
    if prompt_update.metadata_ is not None and prompt_update.metadata_ != db_prompt.metadata_:
        changes["metadata"] = {"old": db_prompt.metadata_, "new": prompt_update.metadata_}
        db_prompt.metadata_ = prompt_update.metadata_
    
    # Status is now managed automatically - no manual status updates in regular updates
    
    # Only update if there are changes
    if changes:
        db_prompt.updated_at = datetime.utcnow()
        db.add(db_prompt)
        db.commit()
        db.refresh(db_prompt)
        
        # Log the update
        _log_prompt_change(
            db=db,
            prompt_id=db_prompt.id,
            version=db_prompt.version,
            changed_by=updated_by,
            action="update",
            changes=changes
        )
    
    return db_prompt

def delete_prompt(db: Session, db_prompt: models.Prompt, deleted_by: str) -> bool:
    """Soft delete a prompt by marking it as archived"""
    if not db_prompt:
        return False
    
    # Log before deleting
    _log_prompt_change(
        db=db,
        prompt_id=db_prompt.id,
        version=db_prompt.version,
        changed_by=deleted_by,
        action="delete",
        changes={"status": str(db_prompt.status)}
    )
    
    # Soft delete by marking as archived
    db_prompt.status = PromptStatus.ARCHIVED
    db_prompt.is_active = False
    db.add(db_prompt)
    db.commit()
    
    return True

def hard_delete_prompt(db: Session, db_prompt: models.Prompt) -> bool:
    """Permanently delete a prompt from the database"""
    try:
        db.delete(db_prompt)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting prompt: {str(e)}")
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_most_relevant_prompt_id(
    db: Session, 
    user_input: str,
    top_k: int = 5
) -> Optional[int]:
    """
    Find the most relevant active prompt based on user input using LLM semantic search.
    
    Args:
        db: Database session
        user_input: The user's input to match against prompts
        top_k: Number of top candidates to consider
        
    Returns:
        ID of the most relevant prompt, or None if no good match found
    """
    try:
        logger.info(f"Finding most relevant prompt for input: {user_input}")
        
        # First, get all active prompts with their content and metadata
        active_prompts = db.query(models.Prompt).filter(
            models.Prompt.status == 'active',
            models.Prompt.is_active == True
        ).all()
        
        logger.info(f"Found {len(active_prompts)} active prompts in the database")
        
        if not active_prompts:
            logger.warning("No active prompts found in the database")
            return None
            
        # Log the active prompts for debugging
        for i, prompt in enumerate(active_prompts, 1):
            logger.info(f"Active prompt {i}: ID={prompt.id}, Name={prompt.name}, "
                       f"Status={prompt.status}, is_active={prompt.is_active}")
            
        # If there's only one active prompt, return it
        if len(active_prompts) == 1:
            logger.info(f"Only one active prompt found, returning ID: {active_prompts[0].id}")
            return active_prompts[0].id
            
        # Prepare prompt information for LLM
        prompt_info = []
        for prompt in active_prompts:
            prompt_info.append({
                "id": prompt.id,
                "name": prompt.name,
                "content": prompt.content,
                "description": prompt.description or "",
                "tags": ", ".join(prompt.tags) if prompt.tags else "",
                "metadata": json.dumps(prompt.metadata_) if prompt.metadata_ else ""
            })
        
        # Format the prompt for the LLM
        system_prompt = """You are an expert at matching user queries to the most appropriate system prompt. 
        Your goal is to analyze the user's input and select the single most relevant prompt ID from the provided list.
        
        MATCHING GUIDELINES:
        1. For coding/technical questions (Python, algorithms, programming), choose the coding assistant prompt.
        2. For internet/connection/tech issues, choose the tech support prompt.
        3. For mental health/stress/anxiety concerns, choose the mental health support prompt.
        4. For cooking/recipes/food questions, choose the cooking assistant prompt.
        
        INSTRUCTIONS:
        1. Carefully read the user's input and identify the main topic/domain.
        2. Review all available prompts and their metadata (name, tags, content preview).
        3. Select the prompt that best matches the user's intent and domain.
        4. Consider both the content and the context of the query.
        5. If the query is ambiguous but could match multiple domains, choose the most likely one.
        
        RESPONSE FORMAT:
        - Return ONLY the numeric ID of the selected prompt (e.g., "42").
        - If no prompt is relevant, return "none".
        - DO NOT include any other text or explanation in your response.
        
        IMPORTANT: Focus on the user's intent and choose the most appropriate prompt, even if the match isn't perfect.
        """
        
        user_message = f"""USER INPUT:
        {user_input}
        
        AVAILABLE PROMPTS (ID, Name, Content Preview):
        """
        
        # Add a brief preview of each prompt
        for info in prompt_info:
            preview = info['content'][:100] + ('...' if len(info['content']) > 100 else '')
            user_message += f"\nID: {info['id']} | Name: {info['name']}\n"
            user_message += f"Preview: {preview}\n"
            if info['tags']:
                user_message += f"Tags: {info['tags']}\n"
        
        user_message += """
        
        RESPONSE FORMAT:
        Return ONLY the numeric ID of the most relevant prompt, or 'none' if none match.
        Example: "42" or "none"
        
        YOUR RESPONSE (ID only):"""
        
        # Log the prompt info being sent to the LLM
        logger.info(f"Sending {len(prompt_info)} prompts to LLM for analysis")
        logger.debug(f"System prompt: {system_prompt}")
        logger.debug(f"User message: {user_message}")
        
        try:
            # Call the LLM to determine the most relevant prompt
            logger.info("Initializing GROQ client...")
            client = Groq(api_key=settings.GROQ_API_KEY)
            
            logger.info("Sending request to GROQ API...")
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=10
            )
            logger.info("Received response from GROQ API")
            logger.debug(f"GROQ API response: {response}")
        except Exception as e:
            logger.error(f"Error calling GROQ API: {str(e)}", exc_info=True)
            raise
        
        # Parse the response to get the prompt ID
        result = response.choices[0].message.content.strip()
        logger.info(f"LLM raw response: {result} for input: {user_input}")
        
        # Clean and extract the prompt ID from the response
        try:
            # Try to find a number in the response (in case the LLM adds text around the ID)
            import re
            numbers = re.findall(r'\d+', result)
            
            if numbers:
                prompt_id = int(numbers[0])  # Take the first number found
                logger.info(f"Extracted prompt ID: {prompt_id}")
                
                # Verify the prompt exists and is active
                prompt = db.query(models.Prompt).filter(
                    models.Prompt.id == prompt_id,
                    models.Prompt.status == 'active',
                    models.Prompt.is_active == True
                ).first()
                
                if prompt:
                    logger.info(f"Valid active prompt found: ID={prompt_id}, Name={prompt.name}")
                    return prompt_id
                else:
                    logger.warning(f"Prompt ID {prompt_id} is not active or doesn't exist")
            else:
                logger.warning(f"No numeric ID found in LLM response: {result}")
                
            return None
                
        except (ValueError, TypeError, Exception) as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.debug(f"Full LLM response: {result}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error finding relevant prompt: {str(e)}", exc_info=True)
        return None

def is_prompt_referenced(db: Session, prompt_id: int) -> bool:
    """Check if a prompt is referenced by other resources"""
    # Add reference checks here if needed in the future
    return False

def search_prompts(
    db: Session,
    query: str = "",
    status: Optional[PromptStatus] = None,
    tag: Optional[str] = None,
    created_by: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[Prompt], int]:
    """
    Search prompts with filters
    Returns: (list_of_prompts, total_count)
    """
    # Start with base query
    base_query = db.query(Prompt)
    
    # Apply filters
    if query:
        search = f"%{query}%"
        base_query = base_query.filter(
            or_(
                Prompt.name.ilike(search),
                Prompt.content.ilike(search),
                Prompt.description.ilike(search)
            )
        )
    
    if status:
        base_query = base_query.filter(Prompt.status == status)
    
    if tag:
        # Use SQLite compatible JSON search for tags
        from sqlalchemy import func
        base_query = base_query.filter(func.json_extract(Prompt.tags, '$').like(f'%"{tag}"%'))
    
    if created_by:
        base_query = base_query.filter(Prompt.created_by == created_by)
    
    # Get total count
    total = base_query.count()
    
    # Apply pagination and order
    prompts = base_query.order_by(
        Prompt.updated_at.desc()
    ).offset(skip).limit(limit).all()
    
    return prompts, total

def get_prompt_history(
    db: Session, 
    prompt_id: int,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[PromptHistory], int]:
    """
    Get change history for a prompt
    Returns: (list_of_history_items, total_count)
    """
    query = db.query(PromptHistory).filter(
        PromptHistory.prompt_id == prompt_id
    )
    
    total = query.count()
    history = query.order_by(
        PromptHistory.changed_at.desc()
    ).offset(skip).limit(limit).all()
    
    return history, total


def set_active_version(db: Session, db_prompt: models.Prompt, updated_by: str) -> models.Prompt:
    """
    Set a specific prompt version as the live version with automatic lifecycle management.
    
    Args:
        db: Database session
        db_prompt: The prompt to set as live
        updated_by: Email or identifier of the user performing the activation
        
    Returns:
        The updated prompt with is_active=True and status=active
    """
    # Find and archive any currently active version
    existing_active = db.query(Prompt).filter(
        Prompt.name == db_prompt.name,
        Prompt.is_active == True,
        Prompt.id != db_prompt.id
    ).first()
    
    if existing_active:
        # Archive the previously active version
        existing_active.status = PromptStatus.ARCHIVED
        existing_active.is_active = False
        existing_active.updated_at = datetime.utcnow()
        db.add(existing_active)
        
        # Log the auto-archival
        _log_prompt_change(
            db=db,
            prompt_id=existing_active.id,
            version=existing_active.version,
            changed_by="system",
            action="auto_archived",
            changes={"status": "active -> archived", "reason": f"replaced by v{db_prompt.version}"}
        )
    
    # Set this version as the live version
    db_prompt.is_active = True
    db_prompt.status = PromptStatus.ACTIVE
    db_prompt.updated_at = datetime.utcnow()
    
    # Log the activation
    _log_prompt_change(
        db=db,
        prompt_id=db_prompt.id,
        version=db_prompt.version,
        changed_by=updated_by,
        action="set_as_live_version"
    )
    
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    
    return db_prompt
