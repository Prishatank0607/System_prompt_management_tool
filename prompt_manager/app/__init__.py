"""
Prompt Management Service - A service for managing and versioning AI prompts.
"""

__version__ = "0.1.0"
__author__ = "Prompt Engineering Team"
__license__ = "Proprietary"

# Import core components for easier access
from .core.config import settings  # noqa
from .core.logger import get_logger  # noqa

__all__ = ["settings", "get_logger"]
