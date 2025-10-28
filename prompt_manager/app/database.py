from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from .core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # SQLite specific
        "timeout": 30,  # 30 second timeout for SQLite
    } if "sqlite" in settings.DATABASE_URL else {
        "connect_timeout": 10,  # 10 second timeout for other databases
    },
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=300,    # Recycle connections after 5 minutes
    pool_timeout=30,     # 30 second timeout for getting a connection from the pool
    max_overflow=10,     # Allow up to 10 connections beyond pool_size
    pool_size=5,         # Maintain 5 persistent connections
    echo=settings.LOG_LEVEL == "DEBUG"  # Enable SQL logging in debug mode
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import all models to ensure they are registered with SQLAlchemy
from .models import prompt, user  # noqa

# Base class for all models
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that yields database sessions.
    Handles session lifecycle automatically.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Creating new database session")
    
    db = SessionLocal()
    try:
        logger.info("Yielding database session")
        yield db
        logger.info("Database session usage completed")
    except Exception as e:
        logger.error(f"Error in database session: {str(e)}")
        raise
    finally:
        logger.info("Closing database session")
        db.close()
        logger.info("Database session closed")
