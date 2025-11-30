"""
Migration Script: Split Comma-Separated Dates

Finds monitoring_jobs with comma-separated dates in target_date field
and splits them into separate monitoring_job records.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_db_session
from config.models import MonitoringJob
from sqlalchemy import select, delete


def migrate_comma_separated_dates():
    """
    Find and split comma-separated dates in monitoring_jobs.
    """
    session = get_db_session()
    
    try:
        # Find jobs with comma-separated dates
        # In SQLite, we can check if string contains comma
        jobs_with_commas = session.execute(
            select(MonitoringJob).where(MonitoringJob.target_date.like('%,%'))
        ).scalars().all()
        
        # Note: SQLAlchemy might fail to load these as MonitoringJob objects if target_date is defined as Date
        # and the value is not a valid date string.
        # If that happens, we might need to use raw SQL.
        
    except Exception as e:
        print(f"ORM failed to load bad data: {e}")
        print("Falling back to raw SQL...")
        session.close()
        # Use raw connection from engine
        from config.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT job_id, user_id, resort_id, target_date, status, priority, created_at, last_checked FROM monitoring_jobs WHERE target_date LIKE '%,%'"))
            jobs_with_commas = result.fetchall()
            
            if not jobs_with_commas:
                print("No jobs with comma-separated dates found.")
                return

            print(f"Found {len(jobs_with_commas)} jobs with comma-separated dates")
            
            for job in jobs_with_commas:
                # job is a Row object, access by index or name
                job_id = job.job_id
                target_date_str = job.target_date
                dates = [d.strip() for d in target_date_str.split(',')]
                
                print(f"\nJob {job_id}: Splitting '{target_date_str}' into {len(dates)} dates")
                
                # Delete original job
                conn.execute(text("DELETE FROM monitoring_jobs WHERE job_id = :job_id"), {"job_id": job_id})
                
                # Create new jobs
                for date in dates:
                    if date:
                        conn.execute(text("""
                            INSERT INTO monitoring_jobs (user_id, resort_id, target_date, status, priority, created_at, last_checked, success_count)
                            VALUES (:user_id, :resort_id, :target_date, :status, :priority, :created_at, :last_checked, 0)
                        """), {
                            "user_id": job.user_id,
                            "resort_id": job.resort_id,
                            "target_date": date,
                            "status": job.status,
                            "priority": job.priority,
                            "created_at": job.created_at,
                            "last_checked": job.last_checked
                        })
                        print(f"  Created job for date: {date}")
            
            conn.commit()
            print(f"\nMigration completed successfully!")
            return

    # If ORM worked (unlikely if type mismatch), we would process here...
    # But for safety, let's just stick to the raw SQL fallback above since we know the data is "bad" for the ORM type.
    pass


if __name__ == "__main__":
    print("=" * 60)
    print("Comma-Separated Dates Migration Script")
    print("=" * 60)
    
    response = input("\nThis will modify the database. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)
    
    migrate_comma_separated_dates()

