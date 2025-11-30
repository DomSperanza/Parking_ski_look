"""
Database Configuration and Management (SQLAlchemy)

Handles database setup, connections, and initialization using SQLAlchemy ORM.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
from sqlalchemy import create_engine, select, delete, update, and_, func
from sqlalchemy.orm import sessionmaker, scoped_session
from config.models import Base, User, Resort, MonitoringJob, Notification, CheckLog

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "parking_monitor.db"
BACKUP_DIR = Path(__file__).parent.parent / "backups"

# Ensure data directory exists
DB_DIR.mkdir(exist_ok=True)

# SQLAlchemy Engine and Session
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """
    Get a new database session.
    
    Returns:
        sqlalchemy.orm.Session: Database session
    """
    return SessionLocal()

def init_database():
    """
    Initialize the database with all required tables.
    """
    logger.info("Initializing database...")
    
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        
        # Insert default resorts if they don't exist
        session = get_db_session()
        try:
            default_resorts = [
                {'name': 'Brighton', 'url': 'https://reservenski.parkbrightonresort.com/select-parking', 'avail': 'rgba(49, 200, 25, 0.2)', 'unavail': 'rgba(247, 205, 212, 1)'},
                {'name': 'Solitude', 'url': 'https://reservenski.parksolitude.com/select-parking', 'avail': 'rgba(49, 200, 25, 0.2)', 'unavail': 'rgba(247, 205, 212, 1)'},
                {'name': 'Alta', 'url': 'https://reserve.altaparking.com/select-parking', 'avail': 'rgba(49, 200, 25, 0.2)', 'unavail': 'rgba(247, 205, 212, 1)'},
                {'name': 'Park City', 'url': 'https://reserve.parkatparkcitymountain.com/select-parking', 'avail': 'rgba(49, 200, 25, 0.2)', 'unavail': 'rgba(247, 205, 212, 1)'}
            ]
            
            for r_data in default_resorts:
                existing = session.execute(select(Resort).where(Resort.resort_name == r_data['name'])).scalar_one_or_none()
                if not existing:
                    resort = Resort(
                        resort_name=r_data['name'],
                        resort_url=r_data['url'],
                        available_color=r_data['avail'],
                        unavailable_color=r_data['unavail'],
                        check_interval=10
                    )
                    session.add(resort)
            
            session.commit()
            logger.info("Database initialized successfully!")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error seeding default data: {e}")
            raise
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def backup_database():
    """
    Create a backup of the database.
    """
    if not DB_PATH.exists():
        logger.warning("Database file does not exist, cannot create backup")
        return None
    
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"parking_monitor_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_filename
    
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return str(backup_path)
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def get_active_monitoring_jobs():
    """
    Get all active monitoring jobs.
    Returns list of dictionaries to maintain compatibility.
    """
    session = get_db_session()
    try:
        stmt = (
            select(MonitoringJob, Resort, User)
            .join(Resort, MonitoringJob.resort_id == Resort.resort_id)
            .join(User, MonitoringJob.user_id == User.user_id)
            .where(MonitoringJob.status == 'active')
            .order_by(MonitoringJob.priority.desc(), MonitoringJob.created_at.asc())
        )
        results = session.execute(stmt).all()
        
        jobs = []
        for job, resort, user in results:
            jobs.append({
                'job_id': job.job_id,
                'user_id': job.user_id,
                'target_date': job.target_date.strftime('%Y-%m-%d') if hasattr(job.target_date, 'strftime') else str(job.target_date),
                'resort_id': job.resort_id,
                'resort_name': resort.resort_name,
                'resort_url': resort.resort_url,
                'available_color': resort.available_color,
                'unavailable_color': resort.unavailable_color,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        return jobs
    except Exception as e:
        logger.error(f"Error fetching active jobs: {e}")
        return []
    finally:
        session.close()

def get_user_selections(user_id):
    """
    Get user's resort and date selections.
    """
    session = get_db_session()
    try:
        stmt = (
            select(MonitoringJob, Resort)
            .join(Resort, MonitoringJob.resort_id == Resort.resort_id)
            .where(MonitoringJob.user_id == user_id)
            .order_by(Resort.resort_name, MonitoringJob.target_date)
        )
        results = session.execute(stmt).all()
        
        selections = []
        for job, resort in results:
            selections.append({
                'job_id': job.job_id,
                'target_date': job.target_date.strftime('%Y-%m-%d') if hasattr(job.target_date, 'strftime') else str(job.target_date),
                'resort_name': resort.resort_name,
                'resort_url': resort.resort_url,
                'status': job.status,
                'created_at': job.created_at
            })
        return selections
    except Exception as e:
        logger.error(f"Error fetching user selections: {e}")
        return []
    finally:
        session.close()

def get_all_users_with_selections():
    """
    Get all users with their selections.
    """
    session = get_db_session()
    try:
        stmt = (
            select(User, MonitoringJob, Resort)
            .outerjoin(MonitoringJob, User.user_id == MonitoringJob.user_id)
            .outerjoin(Resort, MonitoringJob.resort_id == Resort.resort_id)
            .order_by(User.user_id, Resort.resort_name, MonitoringJob.target_date)
        )
        results = session.execute(stmt).all()
        
        users_map = {}
        for user, job, resort in results:
            if user.user_id not in users_map:
                users_map[user.user_id] = {
                    'user_id': user.user_id,
                    'email': user.email,
                    'pin_hash': (user.pin[:16] + '...') if user.pin else '',
                    'created_at': user.created_at,
                    'selections': []
                }
            
            if resort and job:
                users_map[user.user_id]['selections'].append({
                    'resort_name': resort.resort_name,
                    'target_date': job.target_date,
                    'job_status': job.status
                })
        
        return list(users_map.values())
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        return []
    finally:
        session.close()

def log_check_result(resort_id, status, response_time=None, error_message=None, availability_found=False):
    """
    Log monitoring check result.
    """
    session = get_db_session()
    try:
        log = CheckLog(
            resort_id=resort_id,
            status=status,
            response_time=response_time,
            error_message=error_message,
            availability_found=availability_found
        )
        session.add(log)
        session.commit()
        logger.info(f"Logged check result for resort {resort_id}: {status}")
    except Exception as e:
        logger.error(f"Error logging check result: {e}")
        session.rollback()
    finally:
        session.close()

def delete_user_and_jobs(user_id):
    """
    Delete user and all associated data.
    """
    session = get_db_session()
    try:
        # Delete user (cascade will handle jobs and notifications)
        stmt = delete(User).where(User.user_id == user_id)
        result = session.execute(stmt)
        session.commit()
        
        logger.info(f"Deleted user {user_id}")
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def delete_monitoring_job(job_id, user_id):
    """
    Delete a specific monitoring job.
    """
    session = get_db_session()
    try:
        stmt = delete(MonitoringJob).where(and_(
            MonitoringJob.job_id == job_id,
            MonitoringJob.user_id == user_id
        ))
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def delete_expired_jobs():
    """
    Delete monitoring jobs for dates that have passed.
    """
    session = get_db_session()
    try:
        today = datetime.now().date()
        stmt = delete(MonitoringJob).where(MonitoringJob.target_date < today)
        result = session.execute(stmt)
        session.commit()
        
        if result.rowcount > 0:
            logger.info(f"Cleaned up {result.rowcount} expired monitoring jobs")
        return result.rowcount
    except Exception as e:
        logger.error(f"Error cleaning up expired jobs: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

def create_user(email, pin, first_name=None, last_name=None, timezone='America/Denver'):
    """
    Create a new user.
    """
    session = get_db_session()
    try:
        # Check if user exists
        existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            logger.warning(f"User with email {email} already exists")
            return None
            
        user = User(
            email=email,
            pin=pin,
            first_name=first_name,
            last_name=last_name,
            timezone=timezone
        )
        session.add(user)
        session.commit()
        logger.info(f"Created user: {email} (ID: {user.user_id})")
        return user.user_id
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def create_monitoring_job(user_id, resort_id, target_date, priority=1):
    """
    Create a new monitoring job.
    """
    session = get_db_session()
    try:
        # Ensure target_date is a date object if passed as string
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            
        job = MonitoringJob(
            user_id=user_id,
            resort_id=resort_id,
            target_date=target_date,
            priority=priority
        )
        session.add(job)
        session.commit()
        logger.info(f"Created monitoring job: User {user_id}, Resort {resort_id}, Date {target_date}")
        return job.job_id
    except Exception as e:
        logger.error(f"Error creating monitoring job: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def get_user_by_email_and_pin(email, pin):
    """
    Get user by email and PIN.
    """
    session = get_db_session()
    try:
        user = session.execute(
            select(User).where(and_(User.email == email, User.pin == pin))
        ).scalar_one_or_none()
        
        if user:
            return {
                'user_id': user.user_id,
                'email': user.email,
                'pin': user.pin,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'timezone': user.timezone,
                'created_at': user.created_at
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None
    finally:
        session.close()

def get_user_monitoring_jobs(user_id):
    """
    Get all monitoring jobs for a user.
    """
    session = get_db_session()
    try:
        stmt = (
            select(MonitoringJob, Resort)
            .join(Resort, MonitoringJob.resort_id == Resort.resort_id)
            .where(MonitoringJob.user_id == user_id)
            .order_by(MonitoringJob.created_at.desc())
        )
        results = session.execute(stmt).all()
        
        jobs = []
        for job, resort in results:
            jobs.append({
                'job_id': job.job_id,
                'target_date': job.target_date,
                'status': job.status,
                'created_at': job.created_at,
                'success_count': job.success_count,
                'resort_name': resort.resort_name
            })
        return jobs
    except Exception as e:
        logger.error(f"Error fetching user jobs: {e}")
        return []
    finally:
        session.close()

def update_job_last_checked(job_id, timestamp=None):
    """
    Update last_checked timestamp.
    """
    if timestamp is None:
        timestamp = datetime.now()
        
    session = get_db_session()
    try:
        stmt = (
            update(MonitoringJob)
            .where(MonitoringJob.job_id == job_id)
            .values(last_checked=timestamp)
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating job: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def increment_job_success_count(job_id):
    """
    Increment success count.
    """
    session = get_db_session()
    try:
        stmt = (
            update(MonitoringJob)
            .where(MonitoringJob.job_id == job_id)
            .values(success_count=MonitoringJob.success_count + 1)
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error incrementing success count: {e}")
        session.rollback()
        return False
    finally:
        session.close()



def mark_job_notified(job_id):
    """
    Mark job as notified (paused).
    """
    session = get_db_session()
    try:
        stmt = (
            update(MonitoringJob)
            .where(MonitoringJob.job_id == job_id)
            .values(status='notified')
        )
        result = session.execute(stmt)
        session.commit()
        logger.info(f"Marked job {job_id} as notified")
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error marking job notified: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def reactivate_job(job_id):
    """
    Reactivate a notified job.
    """
    session = get_db_session()
    try:
        stmt = (
            update(MonitoringJob)
            .where(MonitoringJob.job_id == job_id)
            .values(status='active')
        )
        result = session.execute(stmt)
        session.commit()
        logger.info(f"Reactivated job {job_id}")
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error reactivating job: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def get_job_by_id(job_id):
    """
    Get job details by ID.
    """
    session = get_db_session()
    try:
        stmt = (
            select(MonitoringJob, Resort, User)
            .join(Resort, MonitoringJob.resort_id == Resort.resort_id)
            .join(User, MonitoringJob.user_id == User.user_id)
            .where(MonitoringJob.job_id == job_id)
        )
        result = session.execute(stmt).first()
        
        if result:
            job, resort, user = result
            return {
                'job_id': job.job_id,
                'user_id': job.user_id,
                'target_date': job.target_date,
                'status': job.status,
                'resort_name': resort.resort_name,
                'resort_url': resort.resort_url,
                'email': user.email
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        return None
    finally:
        session.close()

def create_notification(job_id, user_id, resort_name, available_date):
    """
    Create notification.
    """
    session = get_db_session()
    try:
        # Ensure available_date is a date object
        if isinstance(available_date, str):
            available_date = datetime.strptime(available_date, '%Y-%m-%d').date()
            
        notif = Notification(
            job_id=job_id,
            user_id=user_id,
            resort_name=resort_name,
            available_date=available_date,
            delivery_status='sent'
        )
        session.add(notif)
        session.commit()
        logger.info(f"Created notification {notif.notification_id} for job {job_id}")
        return notif.notification_id
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def get_notification_history(user_id, limit=50):
    """
    Get notification history.
    """
    session = get_db_session()
    try:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.sent_at.desc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()
        
        return [{
            'notification_id': n.notification_id,
            'job_id': n.job_id,
            'sent_at': n.sent_at,
            'delivery_status': n.delivery_status,
            'resort_name': n.resort_name,
            'available_date': n.available_date
        } for n in results]
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []
    finally:
        session.close()

def check_recent_notification(job_id, minutes=30):
    """
    Check for recent notifications.
    """
    session = get_db_session()
    try:
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        stmt = (
            select(Notification)
            .where(and_(
                Notification.job_id == job_id,
                Notification.sent_at > cutoff_time
            ))
        )
        result = session.execute(stmt).first()
        return result is not None
    except Exception as e:
        logger.error(f"Error checking recent notification: {e}")
        return False
    finally:
        session.close()

def create_user_and_jobs(email, pin, resorts, dates):
    """
    Create user and monitoring jobs.
    """
    import hashlib
    import uuid
    
    session = get_db_session()
    try:
        # Create hash
        combined = f"{email.lower().strip()}:{pin}"
        user_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        
        # Check if user exists
        user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        
        if user:
            # Verify hash matches
            if user.pin != user_hash:
                raise Exception("User already exists with different credentials")
        else:
            # Create new user
            user = User(
                email=email,
                pin=user_hash,
                first_name='',
                last_name=''
            )
            session.add(user)
            session.flush() # Get ID
            
        # Get resort IDs
        resort_ids = []
        for resort_name in resorts:
            r = session.execute(select(Resort).where(Resort.resort_name == resort_name)).scalar_one_or_none()
            if r:
                resort_ids.append(r.resort_id)
        
        # Parse dates
        dates_to_process = []
        for date_item in dates:
            if ',' in date_item:
                dates_to_process.extend(date_item.split(','))
            else:
                dates_to_process.append(date_item)
        
        dates_to_process = [d.strip() for d in dates_to_process if d.strip()]
        
        # Create jobs
        for resort_id in resort_ids:
            for date_str in dates_to_process:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Check if job already exists
                existing_job = session.execute(select(MonitoringJob).where(and_(
                    MonitoringJob.user_id == user.user_id,
                    MonitoringJob.resort_id == resort_id,
                    MonitoringJob.target_date == target_date
                ))).scalar_one_or_none()
                
                if not existing_job:
                    job = MonitoringJob(
                        user_id=user.user_id,
                        resort_id=resort_id,
                        target_date=target_date,
                        status='active'
                    )
                    session.add(job)
        
        session.commit()
        return user.user_id
        
    except Exception as e:
        logger.error(f"Error creating user and jobs: {e}")
        session.rollback()
        raise e
    finally:
        session.close()

def update_user_pin(user_id, new_pin):
    """
    Update user's PIN.
    """
    import hashlib
    session = get_db_session()
    try:
        # Create hash
        # We need the email to salt the hash correctly as per create_user_hash logic
        # But wait, create_user_hash uses email + pin.
        # So we need to fetch the user first to get the email.
        
        user = session.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
        if not user:
            return False
            
        combined = f"{user.email.lower().strip()}:{new_pin}"
        pin_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        
        user.pin = pin_hash
        session.commit()
        logger.info(f"Updated PIN for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating PIN for user {user_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    init_database()