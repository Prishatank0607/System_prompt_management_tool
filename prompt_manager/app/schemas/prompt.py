from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, ForwardRef
from datetime import datetime
from enum import Enum
from .enums import PromptStatus

# Use string literals for forward references
User = ForwardRef('User')

class PromptBase(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    status: PromptStatus = PromptStatus.DRAFT
    is_active: bool = False
    tags: List[str] = Field(default_factory=list)
    metadata_: Dict[str, Any] = Field(default_factory=dict)

class PromptCreate(BaseModel):
    name: str = Field(..., description="Unique name for the prompt")
    content: str = Field(..., description="The prompt content/template")
    description: Optional[str] = Field(None, description="Description of the prompt")
    tags: Optional[List[str]] = Field(default=[], description="Tags for categorization")
    metadata_: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")
    version: str = "1.0.0"  # Default version for new prompts

class PromptUpdate(BaseModel):
    content: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None)
    # Removed status field - status is now managed automatically

class PromptInDB(PromptBase):
    id: int
    version: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PromptResponse(PromptInDB):
    """Prompt model for API responses"""
    pass

class Prompt(PromptInDB):
    """Prompt model for responses"""
    pass

class PromptHistoryBase(BaseModel):
    prompt_id: int
    version: str
    content: str
    description: Optional[str] = None
    status: PromptStatus
    tags: List[str] = Field(default_factory=list)
    metadata_: Dict[str, Any] = Field(default_factory=dict)
    changed_by: str
    change_reason: Optional[str] = None

class PromptHistoryCreate(PromptHistoryBase):
    pass

class PromptHistoryInDB(PromptHistoryBase):
    id: int
    changed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PromptHistory(PromptHistoryInDB):
    """Prompt history model for responses"""
    pass

class PromptVersionInfo(BaseModel):
    """Basic information about a prompt version"""
    id: int
    version: str
    status: PromptStatus
    created_at: datetime
    created_by: str
    updated_at: datetime
    is_active: bool
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class PromptVersionCreate(BaseModel):
    """Schema for creating a new version of an existing prompt"""
    version: str = Field(..., description="New version number (semantic versioning)")
    content: Optional[str] = Field(None, description="Updated prompt content (optional)")
    description: Optional[str] = Field(None, description="Description of changes in this version")
    tags: Optional[List[str]] = Field(None, description="Updated tags (optional)")
    metadata_: Optional[Dict[str, Any]] = Field(None, description="Updated metadata (optional)")
    # Removed status field - all new versions start as draft
