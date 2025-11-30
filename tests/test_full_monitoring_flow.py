"""
End-to-End Monitoring Flow Test

Tests the complete monitoring flow:
1. Create test user and monitoring job
2. Run single check cycle
3. Verify logs and notifications
4. Clean up test data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import (
    create_user,
    create_monitoring_job,
    get_active_monitoring_jobs,
    get_notification_history,
    get_db_session,
    log_check_result
)
from config.models import User, MonitoringJob, Notification, CheckLog, Resort
from monitoring.parking_scraper_v3 import check_monitoring_jobs
from webapp.app import create_app


def create_test_user():
    """Create a test user."""
    import hashlib
    
    test_email = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
    test_pin = "123456"
    
    # Hash the PIN like the webapp does
    user_hash = hashlib.sha256(f"{test_email.lower().strip()}:{test_pin}".encode('utf-8')).hexdigest()
    
    user_id = create_user(
        email=test_email,
        pin=user_hash,
        first_name="Test",
        last_name="User"
    )
    
    return user_id, test_email


def create_test_job(user_id, resort_id=1, days_ahead=None):
    """Create a test monitoring job."""
    if days_ahead is None:
        # Default to December 13, 2025 (Saturday - weekend, and user confirmed it shows green)
        target_date = "2025-12-13"
    else:
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    
    job_id = create_monitoring_job(
        user_id=user_id,
        resort_id=resort_id,
        target_date=target_date,
        priority=1
    )
    
    return job_id, target_date


def cleanup_test_data(user_id):
    """Clean up test data."""
    session = get_db_session()
    
    try:
        # Delete user (cascade will handle jobs and notifications)
        stmt = delete(User).where(User.user_id == user_id)
        session.execute(stmt)
        session.commit()
        print(f"Cleaned up test data for user {user_id}")
    except Exception as e:
        print(f"Error cleaning up test data: {e}")
        session.rollback()
    finally:
        session.close()


def main():
    """Run the full monitoring flow test."""
    print("=" * 60)
    print("Full Monitoring Flow Test")
    print("=" * 60)
    print("\nNOTE: If you see errors about comma-separated dates,")
    print("run the migration script first: python scripts/migrate_comma_separated_dates.py")
    print("=" * 60)
    
    # Clean up any old test data first (optional, but helps ensure clean test)
    print("\n0. Cleaning any old test data from previous runs...")
    try:
        session = get_db_session()
        # Delete old test users (email ends with @example.com)
        stmt = delete(User).where(User.email.like('%@example.com'))
        result = session.execute(stmt)
        deleted_count = result.rowcount
        session.commit()
        session.close()
        if deleted_count > 0:
            print(f"   Cleaned {deleted_count} old test users")
    except Exception as e:
        print(f"   Note: Could not clean old test data: {e}")
    
    user_id = None
    
    try:
        # Step 1: Create test user
        print("\n1. Creating test user...")
        user_id, test_email = create_test_user()
        print(f"   Created user ID: {user_id}, Email: {test_email}")
        
        # Step 2: Create test monitoring jobs for all 4 resorts (December 13, 2025 - Saturday)
        print("\n2. Creating test monitoring jobs for all 4 resorts...")
        target_date = "2025-12-13"
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        weekday_name = date_obj.strftime('%A')
        
        # Resort IDs: 1=Brighton, 2=Solitude, 3=Alta, 4=Park City
        job_ids = []
        resort_info = {}
        for resort_id in range(1, 5):
            job_id, created_date = create_test_job(user_id, resort_id=resort_id, days_ahead=None)
            job_ids.append(job_id)
            resort_info[job_id] = resort_id
            print(f"   Created job ID: {job_id} for resort {resort_id}, Target date: {target_date}")
        
        print(f"   Total jobs created: {len(job_ids)}")
        print(f"   Target date: {target_date} ({weekday_name}, {date_obj.strftime('%B %d, %Y')})")
        
        # Step 3: Verify jobs are active
        print("\n3. Verifying jobs are active...")
        active_jobs = get_active_monitoring_jobs()
        found_jobs = [j['job_id'] for j in active_jobs if j['job_id'] in job_ids]
        print(f"   Jobs found in active jobs: {len(found_jobs)}/{len(job_ids)}")
        
        if len(found_jobs) != len(job_ids):
            missing = set(job_ids) - set(found_jobs)
            print(f"   ERROR: Missing jobs: {missing}")
            return
        
        # Step 4: Run single check cycle (headless mode)
        print("\n4. Running single check cycle...")
        print("   (Running in headless mode - checking all 4 resorts for December 13, 2025)")
        
        app = create_app()
        with app.app_context():
            check_monitoring_jobs()
            
        print("   Check cycle completed")
        
        # Step 5: Verify logs were created for all resorts
        print("\n5. Verifying check logs for all resorts...")
        session = get_db_session()
        
        cutoff_time = datetime.now() - timedelta(minutes=5)
        stmt = (
            select(CheckLog.resort_id, func.count(CheckLog.log_id).label('count'))
            .where(CheckLog.resort_id.in_([1, 2, 3, 4]))
            .where(CheckLog.check_timestamp > cutoff_time)
            .group_by(CheckLog.resort_id)
            .order_by(CheckLog.resort_id)
        )
        
        log_results = session.execute(stmt).all()
        total_logs = sum(r.count for r in log_results)
        
        resort_names = {1: 'Brighton', 2: 'Solitude', 3: 'Alta', 4: 'Park City'}
        print(f"   Total check logs created in last 5 minutes: {total_logs}")
        for result in log_results:
            resort_id = result.resort_id
            count = result.count
            resort_name = resort_names.get(resort_id, f'Resort {resort_id}')
            print(f"     - {resort_name} (ID {resort_id}): {count} log(s)")
        
        # Verify all 4 resorts were checked
        checked_resorts = {r.resort_id for r in log_results}
        if len(checked_resorts) < 4:
            missing = set(range(1, 5)) - checked_resorts
            print(f"   WARNING: Missing logs for resort(s): {missing}")
        
        session.close()
        
        # Step 6: Verify notifications (if any were sent)
        print("\n6. Checking notification history...")
        notifications = get_notification_history(user_id)
        print(f"   Notifications sent: {len(notifications)}")
        
        if notifications:
            for notif in notifications:
                print(f"     - {notif['resort_name']} on {notif['available_date']} at {notif['sent_at']}")
        else:
            print("   (No notifications sent - check if dates are available or email is configured)")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERROR during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Step 7: Cleanup
        if user_id:
            print("\n7. Cleaning up test data...")
            cleanup_test_data(user_id)
            print("   Cleanup completed")


if __name__ == "__main__":
    main()
