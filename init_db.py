#!/usr/bin/env python3
"""
Database initialization script for the Prompt Management System.
This script will drop all existing tables and create new ones.
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

def init_db():
    """Initialize the database by creating necessary tables if they don't exist."""
    try:
        # Import here to ensure the path is set correctly
        from prompt_manager.app.database import engine, Base
        from prompt_manager.app.models import Prompt, PromptHistory
        from prompt_manager.app.models.user import User
        
        print("🔨 Initializing database...")
        
        # Only create tables that don't exist
        print("🛠️  Creating tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        
        # Verify the database file was created
        db_dir = project_root / "data" / "db"
        db_path = db_dir / "prompts.db"
        if db_path.exists():
            print(f"✅ Database initialized successfully at: {db_path}")
        else:
            print(f"⚠️  Database file not found after initialization at: {db_path}")
            print(f"    Please check if the directory exists and is writable: {db_dir}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Prompt Management System - Database Initialization")
    print("=" * 60)
    print("⚠️  This is a safe operation that will only create tables that don't exist.")
    print("    No existing data will be modified or deleted.")
    print("-" * 60)
    
    # Confirm before proceeding
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        sys.exit(0)
        
    if init_db():
        print("\n✅ Database initialization completed successfully!")
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)
