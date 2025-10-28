from enum import Enum

class PromptStatus(str, Enum):
    """Enum for prompt status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
