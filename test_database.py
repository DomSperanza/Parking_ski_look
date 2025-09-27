#!/usr/bin/env python3
"""
Database Testing Script

Test the database functionality with sample data.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add config to path
sys.path.append(str(Path(__file__).parent))

from config.database import (
    init_database, 
    create_user, 
    create_monitoring_job,
    get_user_by_email_and_pin,
    get_user_monitoring_jobs,
    get_active_monitoring_jobs,
    log_check_result
)

def test_database():
    """Test database functionality with sample data."""
    print("🧪 Testing Database Functionality...")
    print("=" * 50)
    
    try:
        # Initialize database
        print("1. Initializing database...")
        init_database()
        print("   ✅ Database initialized")
        
        # Create test users
        print("\n2. Creating test users...")
        user1_id = create_user(
            email="john.doe@example.com",
            pin="123456",
            first_name="John",
            last_name="Doe"
        )
        user2_id = create_user(
            email="jane.smith@example.com", 
            pin="789012",
            first_name="Jane",
            last_name="Smith"
        )
        print(f"   ✅ Created users: {user1_id}, {user2_id}")
        
        # Create monitoring jobs
        print("\n3. Creating monitoring jobs...")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # User 1: Brighton tomorrow, Solitude next week
        job1 = create_monitoring_job(user1_id, 1, tomorrow, priority=2)  # Brighton
        job2 = create_monitoring_job(user1_id, 2, next_week, priority=1)  # Solitude
        
        # User 2: Alta tomorrow
        job3 = create_monitoring_job(user2_id, 3, tomorrow, priority=3)  # Alta
        
        print(f"   ✅ Created jobs: {job1}, {job2}, {job3}")
        
        # Test user lookup
        print("\n4. Testing user lookup...")
        user = get_user_by_email_and_pin("john.doe@example.com", "123456")
        if user:
            print(f"   ✅ Found user: {user['first_name']} {user['last_name']}")
        else:
            print("   ❌ User not found")
        
        # Test user jobs
        print("\n5. Testing user jobs...")
        jobs = get_user_monitoring_jobs(user1_id)
        print(f"   ✅ User {user1_id} has {len(jobs)} jobs:")
        for job in jobs:
            print(f"      - {job['resort_name']} on {job['target_date']} ({job['status']})")
        
        # Test active jobs
        print("\n6. Testing active jobs...")
        active_jobs = get_active_monitoring_jobs()
        print(f"   ✅ Found {len(active_jobs)} active jobs:")
        for job in active_jobs:
            print(f"      - {job['resort_name']} for {job['email']} on {job['target_date']}")
        
        # Test logging
        print("\n7. Testing check logging...")
        log_check_result(1, "success", 1500, availability_found=False)
        log_check_result(2, "success", 1200, availability_found=True)
        log_check_result(3, "failed", error_message="Element not found")
        print("   ✅ Logged check results")
        
        print("\n🎉 All database tests passed!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database()
