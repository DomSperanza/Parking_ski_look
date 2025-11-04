"""
Database Configuration and Management

Handles SQLite database setup, connections, and initialization.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = Path(__file__).parent.parent / "data" / "parking_monitor.db"
BACKUP_DIR = Path(__file__).parent.parent / "backups"

def get_db_connection():
    """
    Get a database connection.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    # Create data directory if it doesn't exist
    DB_PATH.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def init_database():
    """
    Initialize the database with all required tables.
    """
    logger.info("Initializing database...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                pin TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                timezone TEXT DEFAULT 'America/Denver',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP
            )
        ''')
        
        # Create resorts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resorts (
                resort_id INTEGER PRIMARY KEY AUTOINCREMENT,
                resort_name TEXT UNIQUE NOT NULL,
                resort_url TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                available_color TEXT,
                unavailable_color TEXT,
                check_interval INTEGER DEFAULT 10
            )
        ''')
        
        # Create monitoring_jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                resort_id INTEGER NOT NULL,
                target_date DATE NOT NULL,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (resort_id) REFERENCES resorts (resort_id)
            )
        ''')
        
        # Create notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_status TEXT DEFAULT 'sent',
                resort_name TEXT,
                available_date DATE,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (job_id) REFERENCES monitoring_jobs (job_id)
            )
        ''')
        
        # Create check_logs table for monitoring system
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS check_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                resort_id INTEGER NOT NULL,
                check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                response_time INTEGER,
                error_message TEXT,
                availability_found BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (resort_id) REFERENCES resorts (resort_id)
            )
        ''')
        
        # Insert default resorts data
        cursor.execute('''
            INSERT OR IGNORE INTO resorts (resort_name, resort_url, available_color, unavailable_color, check_interval)
            VALUES 
                ('Brighton', 'https://reservenski.parkbrightonresort.com/select-parking', 'rgba(49, 200, 25, 0.2)', 'rgba(247, 205, 212, 1)', 10),
                ('Solitude', 'https://reservenski.parksolitude.com/select-parking', 'rgba(49, 200, 25, 0.2)', 'rgba(247, 205, 212, 1)', 10),
                ('Alta', 'https://reserve.altaparking.com/select-parking', 'rgba(49, 200, 25, 0.2)', 'rgba(247, 205, 212, 1)', 10),
                ('Park City', 'https://reserve.parkatparkcitymountain.com/select-parking', 'rgba(49, 200, 25, 0.2)', 'rgba(247, 205, 212, 1)', 10)
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully!")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def backup_database():
    """
    Create a backup of the database.
    
    Returns:
        str: Path to the backup file
    """
    if not DB_PATH.exists():
        logger.warning("Database file does not exist, cannot create backup")
        return None
    
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"parking_monitor_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_filename
    
    try:
        # Copy database file
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return str(backup_path)
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def get_active_monitoring_jobs():
    """
    Get all active monitoring jobs for the scraping system.
    
    Returns:
        list: List of active monitoring jobs
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                j.job_id,
                j.user_id,
                j.target_date,
                j.resort_id,
                r.resort_name,
                r.resort_url,
                r.available_color,
                r.unavailable_color,
                u.email,
                u.first_name,
                u.last_name
            FROM monitoring_jobs j
            JOIN resorts r ON j.resort_id = r.resort_id
            JOIN users u ON j.user_id = u.user_id
            WHERE j.status = 'active'
            ORDER BY j.priority DESC, j.created_at ASC
        ''')
        
        jobs = cursor.fetchall()
        return [dict(job) for job in jobs]
    
    except Exception as e:
        logger.error(f"Error fetching active jobs: {e}")
        return []
    finally:
        conn.close()

def get_user_selections(user_id):
    """
    Get user's resort and date selections from monitoring jobs.
    
    Args:
        user_id (int): User ID to query
        
    Returns:
        list: List of dictionaries with resort and date information
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                mj.job_id,
                mj.target_date,
                r.resort_name,
                r.resort_url,
                mj.status,
                mj.created_at
            FROM monitoring_jobs mj
            JOIN resorts r ON mj.resort_id = r.resort_id
            WHERE mj.user_id = ?
            ORDER BY r.resort_name, mj.target_date
        ''', (user_id,))
        
        jobs = cursor.fetchall()
        return [dict(job) for job in jobs]
    
    except Exception as e:
        logger.error(f"Error fetching user selections: {e}")
        return []
    finally:
        conn.close()

def get_all_users_with_selections():
    """
    Get all users with their resort and date selections.
    Note: PIN field now contains SHA-256 hash, not raw PIN.
    
    Returns:
        list: List of dictionaries with user and selection information
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                u.user_id,
                u.email,
                u.pin as pin_hash,
                u.created_at,
                r.resort_name,
                mj.target_date,
                mj.status as job_status
            FROM users u
            LEFT JOIN monitoring_jobs mj ON u.user_id = mj.user_id
            LEFT JOIN resorts r ON mj.resort_id = r.resort_id
            ORDER BY u.user_id, r.resort_name, mj.target_date
        ''')
        
        results = cursor.fetchall()
        
        # Group by user
        users = {}
        for row in results:
            user_id = row['user_id']
            if user_id not in users:
                users[user_id] = {
                    'user_id': user_id,
                    'email': row['email'],
                    'pin_hash': row['pin_hash'][:16] + '...',  # Show only first 16 chars of hash
                    'created_at': row['created_at'],
                    'selections': []
                }
            
            if row['resort_name']:  # Only add if there are selections
                users[user_id]['selections'].append({
                    'resort_name': row['resort_name'],
                    'target_date': row['target_date'],
                    'job_status': row['job_status']
                })
        
        return list(users.values())
    
    except Exception as e:
        logger.error(f"Error fetching all users with selections: {e}")
        return []
    finally:
        conn.close()

def log_check_result(resort_id, status, response_time=None, error_message=None, availability_found=False):
    """
    Log the result of a monitoring check.
    
    Args:
        resort_id (int): ID of the resort that was checked
        status (str): Status of the check (success, failed, timeout)
        response_time (int, optional): Response time in milliseconds
        error_message (str, optional): Error message if check failed
        availability_found (bool): Whether availability was found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO check_logs (resort_id, status, response_time, error_message, availability_found)
            VALUES (?, ?, ?, ?, ?)
        ''', (resort_id, status, response_time, error_message, availability_found))
        
        conn.commit()
        logger.info(f"Logged check result for resort {resort_id}: {status}")
    
    except Exception as e:
        logger.error(f"Error logging check result: {e}")
    finally:
        conn.close()

def create_user(email, pin, first_name=None, last_name=None, timezone='America/Denver'):
    """
    Create a new user.
    
    Args:
        email (str): User's email address
        pin (str): User's PIN
        first_name (str, optional): User's first name
        last_name (str, optional): User's last name
        timezone (str): User's timezone
    
    Returns:
        int: User ID if successful, None if failed
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (email, pin, first_name, last_name, timezone)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, pin, first_name, last_name, timezone))
        
        conn.commit()
        user_id = cursor.lastrowid
        logger.info(f"Created user: {email} (ID: {user_id})")
        return user_id
    
    except sqlite3.IntegrityError:
        logger.warning(f"User with email {email} already exists")
        return None
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None
    finally:
        conn.close()

def create_monitoring_job(user_id, resort_id, target_date, priority=1):
    """
    Create a new monitoring job.
    
    Args:
        user_id (int): User ID
        resort_id (int): Resort ID
        target_date (str): Target date in YYYY-MM-DD format
        priority (int): Priority level (1=low, 2=medium, 3=high)
    
    Returns:
        int: Job ID if successful, None if failed
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO monitoring_jobs (user_id, resort_id, target_date, priority)
            VALUES (?, ?, ?, ?)
        ''', (user_id, resort_id, target_date, priority))
        
        conn.commit()
        job_id = cursor.lastrowid
        logger.info(f"Created monitoring job: User {user_id}, Resort {resort_id}, Date {target_date}")
        return job_id
    
    except Exception as e:
        logger.error(f"Error creating monitoring job: {e}")
        return None
    finally:
        conn.close()

def get_user_by_email_and_pin(email, pin):
    """
    Get user by email and PIN for status checking.
    
    Args:
        email (str): User's email
        pin (str): User's PIN
    
    Returns:
        dict: User data if found, None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT user_id, email, pin, first_name, last_name, timezone, created_at
            FROM users
            WHERE email = ? AND pin = ?
        ''', (email, pin))
        
        user = cursor.fetchone()
        return dict(user) if user else None
    
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None
    finally:
        conn.close()

def get_user_monitoring_jobs(user_id):
    """
    Get all monitoring jobs for a specific user.
    
    Args:
        user_id (int): User ID
    
    Returns:
        list: List of monitoring jobs
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                j.job_id,
                j.target_date,
                j.status,
                j.created_at,
                j.success_count,
                r.resort_name
            FROM monitoring_jobs j
            JOIN resorts r ON j.resort_id = r.resort_id
            WHERE j.user_id = ?
            ORDER BY j.created_at DESC
        ''', (user_id,))
        
        jobs = cursor.fetchall()
        return [dict(job) for job in jobs]
    
    except Exception as e:
        logger.error(f"Error fetching user jobs: {e}")
        return []
    finally:
        conn.close()

def update_job_last_checked(job_id, timestamp=None):
    """
    Update the last_checked timestamp for a monitoring job.
    
    Args:
        job_id (int): Job ID to update
        timestamp (datetime, optional): Timestamp to set. Defaults to current time.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE monitoring_jobs
            SET last_checked = ?
            WHERE job_id = ?
        ''', (timestamp, job_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating job last_checked: {e}")
        return False
    finally:
        conn.close()

def increment_job_success_count(job_id):
    """
    Increment the success_count for a monitoring job.
    
    Args:
        job_id (int): Job ID to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE monitoring_jobs
            SET success_count = success_count + 1
            WHERE job_id = ?
        ''', (job_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error incrementing job success count: {e}")
        return False
    finally:
        conn.close()

def create_notification(job_id, user_id, resort_name, available_date):
    """
    Create a notification record in the database.
    
    Args:
        job_id (int): Monitoring job ID
        user_id (int): User ID
        resort_name (str): Name of the resort
        available_date (str): Available date in YYYY-MM-DD format
    
    Returns:
        int: Notification ID if successful, None otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO notifications (user_id, job_id, resort_name, available_date, delivery_status)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, job_id, resort_name, available_date, 'sent'))
        
        conn.commit()
        notification_id = cursor.lastrowid
        logger.info(f"Created notification {notification_id} for job {job_id}")
        return notification_id
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None
    finally:
        conn.close()

def get_notification_history(user_id, limit=50):
    """
    Get notification history for a user.
    
    Args:
        user_id (int): User ID
        limit (int): Maximum number of notifications to return
    
    Returns:
        list: List of notification records
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                notification_id,
                job_id,
                sent_at,
                delivery_status,
                resort_name,
                available_date
            FROM notifications
            WHERE user_id = ?
            ORDER BY sent_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        notifications = cursor.fetchall()
        return [dict(notif) for notif in notifications]
    except Exception as e:
        logger.error(f"Error fetching notification history: {e}")
        return []
    finally:
        conn.close()

def check_recent_notification(job_id, minutes=30):
    """
    Check if a notification was sent recently for this job.
    
    Args:
        job_id (int): Job ID to check
        minutes (int): Number of minutes to look back
    
    Returns:
        bool: True if notification sent recently, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # SQLite datetime subtraction syntax
        cursor.execute('''
            SELECT notification_id
            FROM notifications
            WHERE job_id = ?
            AND sent_at > datetime('now', '-' || ? || ' minutes')
        ''', (job_id, str(minutes)))
        
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        logger.error(f"Error checking recent notification: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Initialize database when run directly
    init_database()
    print("Database initialization complete!")