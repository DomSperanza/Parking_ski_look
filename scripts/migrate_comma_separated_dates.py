"""
Migration Script: Split Comma-Separated Dates

Finds monitoring_jobs with comma-separated dates in target_date field
and splits them into separate monitoring_job records.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_db_connection


def migrate_comma_separated_dates():
    """
    Find and split comma-separated dates in monitoring_jobs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find jobs with comma-separated dates
        cursor.execute('''
            SELECT job_id, user_id, resort_id, target_date, status, priority, created_at, last_checked, success_count
            FROM monitoring_jobs
            WHERE target_date LIKE '%,%'
        ''')
        
        jobs_with_commas = cursor.fetchall()
        
        if not jobs_with_commas:
            print("No jobs with comma-separated dates found.")
            return
        
        print(f"Found {len(jobs_with_commas)} jobs with comma-separated dates")
        
        for job in jobs_with_commas:
            job_id = job['job_id']
            dates = [d.strip() for d in job['target_date'].split(',')]
            
            print(f"\nJob {job_id}: Splitting '{job['target_date']}' into {len(dates)} dates")
            
            # Delete the original job
            cursor.execute('DELETE FROM monitoring_jobs WHERE job_id = ?', (job_id,))
            
            # Create new jobs for each date
            for date in dates:
                if date:  # Skip empty strings
                    cursor.execute('''
                        INSERT INTO monitoring_jobs 
                        (user_id, resort_id, target_date, status, priority, created_at, last_checked, success_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        job['user_id'],
                        job['resort_id'],
                        date,
                        job['status'],
                        job['priority'],
                        job['created_at'],
                        job['last_checked'],
                        0  # Reset success_count for new jobs
                    ))
                    print(f"  Created job for date: {date}")
        
        conn.commit()
        print(f"\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Comma-Separated Dates Migration Script")
    print("=" * 60)
    
    response = input("\nThis will modify the database. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)
    
    migrate_comma_separated_dates()

