"""
Flask Application Factory

Creates and configures the Flask application instance.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
import uuid
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_db_connection

def create_user_hash(email, pin):
    """
    Create a SHA-256 hash from email and PIN for secure storage.
    
    Args:
        email (str): User's email address
        pin (str): User's 6-digit PIN
        
    Returns:
        str: SHA-256 hash of email + pin
    """
    # Combine email and pin with a separator
    combined = f"{email.lower().strip()}:{pin}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def get_mountain_time_now():
    """
    Get current time in Mountain Time zone.
    
    Returns:
        datetime: Current time in Mountain Time
    """
    import pytz
    mountain_tz = pytz.timezone('America/Denver')
    return datetime.now(mountain_tz)

def validate_date_in_mountain_time(date_str):
    """
    Validate that a date string is valid and not in the past in Mountain Time.
    
    Args:
        date_str (str): Date string in YYYY-MM-DD format
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Clean the date string
        date_str = date_str.strip()
        
        if not date_str:
            return False, "Empty date"
        
        # Parse the date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get today's date in Mountain Time
        mountain_now = get_mountain_time_now()
        today = mountain_now.date()
        
        if date_obj < today:
            return False, "Date cannot be in the past"
        
        return True, None
        
    except ValueError as e:
        return False, f"Invalid date format: {date_str}. Expected YYYY-MM-DD"
    except Exception as e:
        return False, f"Error validating date: {str(e)}"

def verify_user_credentials(email, pin):
    """
    Verify user credentials and return user_id if valid.
    
    Args:
        email (str): User's email address
        pin (str): User's 6-digit PIN
        
    Returns:
        int or None: User ID if credentials are valid, None otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create hash from provided credentials
        user_hash = create_user_hash(email, pin)
        
        # Check if user exists with matching hash
        cursor.execute('SELECT user_id FROM users WHERE email = ? AND pin = ?', (email, user_hash))
        result = cursor.fetchone()
        
        return result[0] if result else None
        
    except Exception as e:
        print(f"Error verifying credentials: {e}")
        return None
    finally:
        conn.close()

def delete_user_and_jobs(user_id):
    """
    Delete user and all associated monitoring jobs.
    
    Args:
        user_id (int): User ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Delete monitoring jobs first (foreign key constraint)
        cursor.execute('DELETE FROM monitoring_jobs WHERE user_id = ?', (user_id,))
        jobs_deleted = cursor.rowcount
        
        # Delete notifications
        cursor.execute('DELETE FROM notifications WHERE user_id = ?', (user_id,))
        notifications_deleted = cursor.rowcount
        
        # Delete user
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        user_deleted = cursor.rowcount
        
        conn.commit()
        
        print(f"Deleted user {user_id}: {user_deleted} user, {jobs_deleted} jobs, {notifications_deleted} notifications")
        return user_deleted > 0
        
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-change-in-production'
    
    # Optional: Start background monitoring thread (disabled by default)
    # Uncomment to enable monitoring from within Flask app
    # from services.monitoring_daemon import main as monitoring_main
    # import threading
    # monitoring_thread = threading.Thread(target=monitoring_main, daemon=True)
    # monitoring_thread.start()
    
    @app.route('/admin/monitoring/status')
    def monitoring_status():
        """Health check endpoint for monitoring service."""
        from config.database import get_active_monitoring_jobs
        try:
            jobs = get_active_monitoring_jobs()
            return {
                'status': 'ok',
                'active_jobs': len(jobs),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }, 500
    
    @app.route('/')
    def home():
        """Home page with resort selection and date picker."""
        return render_template('home.html')
    
    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        """Contact information page."""
        if request.method == 'POST':
            # Get form data
            selected_resorts = request.form.getlist('resorts')
            selected_dates = request.form.getlist('dates')
            email = request.form.get('email')
            email_confirm = request.form.get('email_confirm')
            pin = request.form.get('pin')
            
            # Validate form data
            if not selected_resorts:
                flash('Please select at least one resort.', 'error')
                return render_template('home.html')
            
            if not selected_dates:
                flash('Please select at least one date.', 'error')
                return render_template('home.html')
            
            # Parse and validate all selected dates
            # selected_dates comes as a list from form.getlist('dates')
            # but if it's a single string with commas, we need to split it
            dates_to_validate = []
            for date_item in selected_dates:
                if ',' in date_item:
                    # Split comma-separated dates
                    dates_to_validate.extend(date_item.split(','))
                else:
                    dates_to_validate.append(date_item)
            
            # Remove empty strings and validate each date
            dates_to_validate = [d.strip() for d in dates_to_validate if d.strip()]
            
            for date_str in dates_to_validate:
                is_valid, error_msg = validate_date_in_mountain_time(date_str)
                if not is_valid:
                    flash(f'Invalid date: {date_str} - {error_msg}', 'error')
                    return render_template('home.html')
            
            if not email or not email_confirm or not pin:
                flash('Please fill in all required fields.', 'error')
                return render_template('contact.html', 
                                     resorts=selected_resorts, 
                                     dates=selected_dates)
            
            if email != email_confirm:
                flash('Email addresses do not match.', 'error')
                return render_template('contact.html', 
                                     resorts=selected_resorts, 
                                     dates=selected_dates)
            
            if not pin.isdigit() or len(pin) != 6:
                flash('PIN must be exactly 6 digits.', 'error')
                return render_template('contact.html', 
                                     resorts=selected_resorts, 
                                     dates=selected_dates)
            
            # Store in session for processing
            session['selected_resorts'] = selected_resorts
            session['selected_dates'] = selected_dates
            session['email'] = email
            session['pin'] = pin
            
            # Process the data
            try:
                user_id = create_user_and_jobs(email, pin, selected_resorts, selected_dates)
                session['user_id'] = str(user_id)
                return redirect(url_for('thank_you'))
            except Exception as e:
                flash(f'Error creating account: {str(e)}', 'error')
                return render_template('contact.html', 
                                     resorts=selected_resorts, 
                                     dates=selected_dates)
        
        # GET request - show contact form
        resorts = request.args.getlist('resorts')
        dates = request.args.getlist('dates')
        return render_template('contact.html', resorts=resorts, dates=dates)
    
    @app.route('/thank-you')
    def thank_you():
        """Thank you page after successful registration."""
        if 'user_id' not in session:
            return redirect(url_for('home'))
        return render_template('thank_you.html')
    
    @app.route('/lookup', methods=['GET', 'POST'])
    def lookup():
        """User lookup page to check their selections."""
        if request.method == 'POST':
            email = request.form.get('email')
            pin = request.form.get('pin')
            
            if not email or not pin:
                flash('Please enter both email and PIN.', 'error')
                return render_template('lookup.html')
            
            if not pin.isdigit() or len(pin) != 6:
                flash('PIN must be exactly 6 digits.', 'error')
                return render_template('lookup.html')
            
            # Verify user credentials
            user_id = verify_user_credentials(email, pin)
            if user_id:
                # Store user info in session for individual deletions
                session['user_id'] = user_id
                session['email'] = email
                session['pin'] = pin
                
                # Get user's selections
                from config.database import get_user_selections
                selections = get_user_selections(user_id)
                return render_template('user_dashboard.html', 
                                     email=email, 
                                     selections=selections,
                                     user_id=user_id)
            else:
                flash('Invalid email or PIN. Please try again.', 'error')
                return render_template('lookup.html')
        
        return render_template('lookup.html')
    
    @app.route('/delete-account', methods=['POST'])
    def delete_account():
        """Delete user account and all monitoring jobs."""
        user_id = request.form.get('user_id')
        
        # Check if user is logged in via session
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('lookup'))
        
        # Verify the user_id matches the session
        if str(session['user_id']) != str(user_id):
            flash('Invalid request. Cannot delete account.', 'error')
            return redirect(url_for('lookup'))
        
        try:
            # Delete user and all associated data
            success = delete_user_and_jobs(user_id)
            if success:
                # Clear the session
                session.clear()
                flash('Your account and all monitoring jobs have been successfully deleted.', 'success')
                return redirect(url_for('home'))
            else:
                flash('Error deleting account. Please try again.', 'error')
                return redirect(url_for('lookup'))
        except Exception as e:
            flash(f'Error deleting account: {str(e)}', 'error')
            return redirect(url_for('lookup'))
    
    @app.route('/delete-job', methods=['POST'])
    def delete_job():
        """Delete a specific monitoring job."""
        job_id = request.form.get('job_id')
        
        # Check if user is logged in via session
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('lookup'))
        
        user_id = session['user_id']
        
        if not job_id:
            flash('Missing job ID.', 'error')
            # Stay on dashboard
            from config.database import get_user_selections
            selections = get_user_selections(user_id)
            return render_template('user_dashboard.html', 
                                 email=session['email'], 
                                 selections=selections,
                                 user_id=user_id)
        
        try:
            # Verify the job belongs to this user
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id FROM monitoring_jobs WHERE job_id = ?', (job_id,))
            result = cursor.fetchone()
            
            if not result or result[0] != user_id:
                flash('Job not found or access denied.', 'error')
                # Stay on dashboard
                from config.database import get_user_selections
                selections = get_user_selections(user_id)
                return render_template('user_dashboard.html', 
                                     email=session['email'], 
                                     selections=selections,
                                     user_id=user_id)
            
            # Delete the job
            cursor.execute('DELETE FROM monitoring_jobs WHERE job_id = ?', (job_id,))
            conn.commit()
            conn.close()
            
            flash('Monitoring job deleted successfully.', 'success')
            
            # Redirect back to dashboard with user's selections
            from config.database import get_user_selections
            selections = get_user_selections(user_id)
            return render_template('user_dashboard.html', 
                                 email=session['email'], 
                                 selections=selections,
                                 user_id=user_id)
            
        except Exception as e:
            flash(f'Error deleting job: {str(e)}', 'error')
            # Stay on dashboard even if there's an error
            from config.database import get_user_selections
            selections = get_user_selections(user_id)
            return render_template('user_dashboard.html', 
                                 email=session['email'], 
                                 selections=selections,
                                 user_id=user_id)
    
    return app

def create_user_and_jobs(email, pin, resorts, dates):
    """Create user and monitoring jobs in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate UUID for user
        user_uuid = str(uuid.uuid4())
        
        # Create secure hash from email + pin
        user_hash = create_user_hash(email, pin)
        
        # Check if user already exists
        cursor.execute('SELECT user_id FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # User exists, check if hash matches (for login verification)
            cursor.execute('SELECT user_id FROM users WHERE email = ? AND pin = ?', (email, user_hash))
            if cursor.fetchone():
                user_id = existing_user[0]
            else:
                raise Exception("User already exists with different credentials")
        else:
            # Create new user with hashed credentials
            cursor.execute('''
                INSERT INTO users (email, pin, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (email, user_hash, '', ''))
            
            user_id = cursor.lastrowid
        
        # Get resort IDs
        resort_ids = []
        for resort_name in resorts:
            cursor.execute('SELECT resort_id FROM resorts WHERE resort_name = ?', (resort_name,))
            result = cursor.fetchone()
            if result:
                resort_ids.append(result[0])
        
        # Parse dates (handle comma-separated string)
        dates_to_process = []
        for date_item in dates:
            if ',' in date_item:
                dates_to_process.extend(date_item.split(','))
            else:
                dates_to_process.append(date_item)
        
        # Remove empty strings and strip whitespace
        dates_to_process = [d.strip() for d in dates_to_process if d.strip()]
        
        # Create monitoring jobs for each resort/date combination
        for resort_id in resort_ids:
            for date in dates_to_process:
                cursor.execute('''
                    INSERT INTO monitoring_jobs (user_id, resort_id, target_date, status)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, resort_id, date, 'active'))
        
        conn.commit()
        return user_id
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
