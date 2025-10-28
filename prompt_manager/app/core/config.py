"""
Application configuration settings.
"""
import os
from typing import Dict, Any, Optional, List, Union
from pydantic import validator, PostgresDsn, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings."""
    
    # Application metadata
    APP_NAME: str = "Prompt Management Service"
    APP_VERSION: str = "1.0.0"
    PROJECT_NAME: str = "Prompt Management Service"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Database
    DB_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../data/db'))
    os.makedirs(DB_DIR, exist_ok=True)
    DB_PATH: str = os.path.join(DB_DIR, 'prompts.db')
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    
    # GROQ API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Initialize settings
settings = Settings()
