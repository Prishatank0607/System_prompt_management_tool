from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from .prompt import PromptStatus

class PromptHistoryItem(BaseModel):
    """History item for prompt version history"""
    id: int
    prompt_id: int
    version: str
    content: str
    description: Optional[str] = None
    status: PromptStatus
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    changed_by: str
    changed_at: datetime
    change_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
