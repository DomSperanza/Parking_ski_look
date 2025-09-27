#!/usr/bin/env python3
"""
Database Initialization Script

Run this script to create and initialize the SQLite database.
"""

import sys
from pathlib import Path

# Add config to path
sys.path.append(str(Path(__file__).parent))

from config.database import init_database, backup_database

def main():
    """Initialize the database and create a backup."""
    print("🚀 Initializing Parking Monitor Database...")
    print("=" * 50)
    
    try:
        # Initialize database
        init_database()
        print("✅ Database initialized successfully!")
        
        # Create initial backup
        backup_path = backup_database()
        if backup_path:
            print(f"✅ Initial backup created: {backup_path}")
        else:
            print("⚠️  Could not create initial backup")
        
        print("\n📊 Database Structure:")
        print("   - users: User accounts and information")
        print("   - resorts: Ski resort configurations")
        print("   - monitoring_jobs: Active monitoring jobs")
        print("   - notifications: Sent notification history")
        print("   - check_logs: System monitoring logs")
        
        print("\n🏔️  Pre-configured Resorts:")
        print("   - Brighton")
        print("   - Solitude") 
        print("   - Alta")
        print("   - Park City")
        
        print("\n🎯 Ready to start monitoring!")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
