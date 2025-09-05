#!/usr/bin/env python3
"""Database management CLI for development."""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
script_dir = Path(__file__).parent
api_root = script_dir.parent
sys.path.insert(0, str(api_root))

from app.core.db_init import init_database, reset_database


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/db_manage.py <command>")
        print("Commands:")
        print("  init     - Create tables if they don't exist")
        print("  reset    - Drop and recreate all tables")
        print("  fresh    - Alias for reset")
        return
    
    command = sys.argv[1].lower()
    
    if command == "init":
        print("Initializing database (creating tables if they don't exist)...")
        await init_database(drop_existing=False)
        print("✅ Database initialization completed")
        
    elif command in ["reset", "fresh"]:
        print("⚠️  This will DROP ALL EXISTING DATA!")
        if "--force" not in sys.argv:
            confirm = input("Are you sure? Type 'yes' to continue: ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return
        
        print("Resetting database (dropping and recreating all tables)...")
        await reset_database()
        print("✅ Database reset completed")
        
    else:
        print(f"Unknown command: {command}")
        print("Available commands: init, reset, fresh")
        return 1


if __name__ == "__main__":
    asyncio.run(main())