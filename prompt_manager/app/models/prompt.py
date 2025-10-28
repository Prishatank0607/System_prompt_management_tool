from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Enum, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from .base import Base

# Using string values directly for SQLAlchemy Enum
PROMPT_STATUS = ["draft", "active", "archived"]

class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(*PROMPT_STATUS, name="prompt_status"), default="draft", nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    tags = Column(JSON, default=[])
    metadata_ = Column("metadata", JSON, default={})
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    history = relationship("PromptHistory", back_populates="prompt", cascade="all, delete-orphan")

class PromptHistory(Base):
    __tablename__ = "prompt_history"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    version = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(*PROMPT_STATUS, name="prompt_status"), nullable=False)
    tags = Column(JSON, default=[])
    metadata_ = Column("metadata", JSON, default={})
    changed_by = Column(String, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    change_reason = Column(Text, nullable=True)
    
    # Relationships
    prompt = relationship("Prompt", back_populates="history")
