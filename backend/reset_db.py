#!/usr/bin/env python3
"""Database reset script for the financial planning application."""

import os
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.append(os.path.dirname(__file__))

from app.db import Base, engine
from app.seeds.seed_v1 import run_seeds

def reset_database():
    """Reset the database by dropping all tables, recreating them, and seeding with data."""
    print("Resetting database...")
    
    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    # Run seeds
    print("Seeding database...")
    run_seeds()
    
    print("Database reset complete!")

if __name__ == "__main__":
    reset_database()
