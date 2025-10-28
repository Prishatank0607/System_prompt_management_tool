"""
Application logging configuration.
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from ..core.config import settings

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = settings.LOG_LEVEL

# Configure root logger
def setup_logging():
    """Configure the root logger with console and file handlers."""
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Set the log level
    numeric_level = getattr(logging, LOG_LEVEL.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    root_logger.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / "app.log")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

# Get a logger for a specific module
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.
    
    Args:
        name: The name of the module (usually __name__)
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    return logger

# Initialize logging when module is imported
setup_logging()
