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
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import (
    get_active_monitoring_jobs,
    get_user_selections,
    create_user_and_jobs,
    delete_user_and_jobs,
    delete_monitoring_job,
    get_user_by_email_and_pin,
    update_user_pin,
    reactivate_job,
    get_job_by_id,
)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature


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
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_mountain_time_now():
    """
    Get current time in Mountain Time zone.

    Returns:
        datetime: Current time in Mountain Time
    """
    import pytz

    mountain_tz = pytz.timezone("America/Denver")
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
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

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
    """
    # Create hash locally to match what's stored (or let database.py handle it?)
    # database.py's get_user_by_email_and_pin expects the HASHED pin if we look at the implementation?
    # Wait, get_user_by_email_and_pin in database.py checks (User.pin == pin).
    # The User.pin stores the hash.
    # So we need to hash it here before passing it.

    combined = f"{email.lower().strip()}:{pin}"
    user_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    user = get_user_by_email_and_pin(email, user_hash)
    return user["user_id"] if user else None


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app = Flask(__name__)
    app.secret_key = os.environ.get(
        "SECRET_KEY", "your-secret-key-change-in-production"
    )

    # Email Configuration
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "True") == "True"
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
        "MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"]
    )

    mail = Mail(app)
    s = URLSafeTimedSerializer(app.secret_key)

    # Optional: Start background monitoring thread (disabled by default)
    # Uncomment to enable monitoring from within Flask app
    # from services.monitoring_daemon import main as monitoring_main
    # import threading
    # monitoring_thread = threading.Thread(target=monitoring_main, daemon=True)
    # monitoring_thread.start()

    @app.route("/admin/monitoring/status")
    def monitoring_status():
        """Health check endpoint for monitoring service."""

        try:
            jobs = get_active_monitoring_jobs()
            return {
                "status": "ok",
                "active_jobs": len(jobs),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

    @app.route("/")
    def home():
        """Home page with resort selection and date picker."""
        return render_template("home.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        """Contact information page."""
        if request.method == "POST":
            # Get form data
            selected_resorts = request.form.getlist("resorts")
            selected_dates = request.form.getlist("dates")
            email = request.form.get("email")
            email_confirm = request.form.get("email_confirm")
            pin = request.form.get("pin")

            # Validate form data
            if not selected_resorts:
                flash("Please select at least one resort.", "error")
                return render_template("home.html")

            if not selected_dates:
                flash("Please select at least one date.", "error")
                return render_template("home.html")

            # Parse and validate all selected dates
            # selected_dates comes as a list from form.getlist('dates')
            # but if it's a single string with commas, we need to split it
            dates_to_validate = []
            for date_item in selected_dates:
                if "," in date_item:
                    # Split comma-separated dates
                    dates_to_validate.extend(date_item.split(","))
                else:
                    dates_to_validate.append(date_item)

            # Remove empty strings and validate each date
            dates_to_validate = [d.strip() for d in dates_to_validate if d.strip()]

            for date_str in dates_to_validate:
                is_valid, error_msg = validate_date_in_mountain_time(date_str)
                if not is_valid:
                    flash(f"Invalid date: {date_str} - {error_msg}", "error")
                    return render_template("home.html")

            if not email or not email_confirm or not pin:
                flash("Please fill in all required fields.", "error")
                return render_template(
                    "contact.html", resorts=selected_resorts, dates=selected_dates
                )

            if email != email_confirm:
                flash("Email addresses do not match.", "error")
                return render_template(
                    "contact.html", resorts=selected_resorts, dates=selected_dates
                )

            if not pin.isdigit() or len(pin) != 6:
                flash("PIN must be exactly 6 digits.", "error")
                return render_template(
                    "contact.html", resorts=selected_resorts, dates=selected_dates
                )

            # Store in session for processing
            session["selected_resorts"] = selected_resorts
            session["selected_dates"] = selected_dates
            session["email"] = email
            session["pin"] = pin

            # Process the data
            try:
                user_id = create_user_and_jobs(
                    email, pin, selected_resorts, selected_dates
                )
                session["user_id"] = str(user_id)
                return redirect(url_for("thank_you"))
            except Exception as e:
                flash(f"Error creating account: {str(e)}", "error")
                return render_template(
                    "contact.html", resorts=selected_resorts, dates=selected_dates
                )

        # GET request - show contact form
        resorts = request.args.getlist("resorts")
        dates = request.args.getlist("dates")
        return render_template("contact.html", resorts=resorts, dates=dates)

    @app.route("/thank-you")
    def thank_you():
        """Thank you page after successful registration."""
        if "user_id" not in session:
            return redirect(url_for("home"))
        return render_template("thank_you.html")

    @app.route("/lookup", methods=["GET", "POST"])
    def lookup():
        """User lookup page to check their selections."""
        if request.method == "POST":
            email = request.form.get("email")
            pin = request.form.get("pin")

            if not email or not pin:
                flash("Please enter both email and PIN.", "error")
                return render_template("lookup.html")

            if not pin.isdigit() or len(pin) != 6:
                flash("PIN must be exactly 6 digits.", "error")
                return render_template("lookup.html")

            # Verify user credentials
            user_id = verify_user_credentials(email, pin)
            if user_id:
                # Store user info in session for individual deletions
                session["user_id"] = user_id
                session["email"] = email
                session["pin"] = pin

                # Get user's selections

                selections = get_user_selections(user_id)
                return render_template(
                    "user_dashboard.html",
                    email=email,
                    selections=selections,
                    user_id=user_id,
                )
            else:
                flash("Invalid email or PIN. Please try again.", "error")
                return render_template("lookup.html")

        return render_template("lookup.html")

    @app.route("/delete-account", methods=["POST"])
    def delete_account():
        """Delete user account and all monitoring jobs."""
        user_id = request.form.get("user_id")

        # Check if user is logged in via session
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("lookup"))

        # Verify the user_id matches the session
        if str(session["user_id"]) != str(user_id):
            flash("Invalid request. Cannot delete account.", "error")
            return redirect(url_for("lookup"))

        try:
            # Delete user and all associated data
            success = delete_user_and_jobs(user_id)
            if success:
                # Clear the session
                session.clear()
                flash(
                    "Your account and all monitoring jobs have been successfully deleted.",
                    "success",
                )
                return redirect(url_for("home"))
            else:
                flash("Error deleting account. Please try again.", "error")
                return redirect(url_for("lookup"))
        except Exception as e:
            flash(f"Error deleting account: {str(e)}", "error")
            return redirect(url_for("lookup"))

    @app.route("/delete-job", methods=["POST"])
    def delete_job():
        """Delete a specific monitoring job."""
        job_id = request.form.get("job_id")

        # Check if user is logged in via session
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("lookup"))

        user_id = session["user_id"]

        if not job_id:
            flash("Missing job ID.", "error")
            # Stay on dashboard

            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

        try:

            flash("Monitoring job deleted successfully.", "success")

            # Redirect back to dashboard with user's selections
            # Delete the job
            success = delete_monitoring_job(job_id, user_id)

            if success:
                flash("Monitoring job deleted successfully.", "success")
            else:
                flash("Job not found or access denied.", "error")
            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

        except Exception as e:
            flash(f"Error deleting job: {str(e)}", "error")
            # Stay on dashboard even if there's an error
            from config.database import get_user_selections

            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

    @app.route("/reactivate-job", methods=["POST"])
    def reactivate_job_route():
        """Reactivate a specific monitoring job manually."""
        job_id = request.form.get("job_id")

        # Check if user is logged in via session
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("lookup"))

        user_id = session["user_id"]

        if not job_id:
            flash("Missing job ID.", "error")
            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

        try:
            # Verify ownership first (get_job_by_id returns job info including user_id)
            job = get_job_by_id(job_id)
            if not job or str(job["user_id"]) != str(user_id):
                flash("Job not found or access denied.", "error")
            else:
                if reactivate_job(job_id):
                    flash(
                        "Monitoring reactivated! We will check this date again.",
                        "success",
                    )
                else:
                    flash("Could not reactivate job.", "error")

            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

        except Exception as e:
            flash(f"Error reactivating job: {str(e)}", "error")
            selections = get_user_selections(user_id)
            return render_template(
                "user_dashboard.html",
                email=session["email"],
                selections=selections,
                user_id=user_id,
            )

    @app.route("/forgot-pin", methods=["GET", "POST"])
    def forgot_pin():
        """Handle forgot PIN requests."""
        if request.method == "POST":
            email = request.form.get("email")
            if not email:
                flash("Please enter your email address.", "error")
                return render_template("forgot_pin.html")

            # Check if user exists (we don't want to leak existence, but for this app it's fine to be vague)
            # Actually, for security, we should always say "If an account exists..."
            # But we need the user_id to verify existence for the token logic if we were storing it,
            # but here we are stateless.

            # However, we should verify the email is in our DB before sending?
            # Yes, let's check.
            from config.database import get_db_session, User
            from sqlalchemy import select

            session_db = get_db_session()
            user = session_db.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            session_db.close()

            if user:
                token = s.dumps(email, salt="reset-pin")
                link = url_for("reset_pin", token=token, _external=True)

                msg = Message("Reset Your Ski Parking Monitor PIN", recipients=[email])
                msg.body = f"Click the link to reset your PIN: {link}\n\nLink expires in 1 hour."

                try:
                    mail.send(msg)
                    flash(
                        "If an account exists with that email, a reset link has been sent.",
                        "success",
                    )
                except Exception as e:
                    print(f"Error sending email: {e}")
                    flash("Error sending email. Please try again later.", "error")
            else:
                # Don't reveal user existence
                flash(
                    "If an account exists with that email, a reset link has been sent.",
                    "success",
                )

            return redirect(url_for("forgot_pin"))

        return render_template("forgot_pin.html")

    @app.route("/reset-pin/<token>", methods=["GET", "POST"])
    def reset_pin(token):
        """Handle PIN reset with token."""
        try:
            email = s.loads(token, salt="reset-pin", max_age=3600)
        except SignatureExpired:
            flash("The reset link has expired.", "error")
            return redirect(url_for("forgot_pin"))
        except BadTimeSignature:
            flash("Invalid reset link.", "error")
            return redirect(url_for("forgot_pin"))

        if request.method == "POST":
            pin = request.form.get("pin")
            pin_confirm = request.form.get("pin_confirm")

            if not pin or len(pin) != 6 or not pin.isdigit():
                flash("PIN must be exactly 6 digits.", "error")
                return render_template("reset_pin.html", token=token)

            if pin != pin_confirm:
                flash("PINs do not match.", "error")
                return render_template("reset_pin.html", token=token)

            # Update PIN
            from config.database import get_db_session, User
            from sqlalchemy import select

            session_db = get_db_session()
            user = session_db.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            user_id = user.user_id if user else None
            session_db.close()

            if user_id:
                if update_user_pin(user_id, pin):
                    flash("Your PIN has been updated. Please log in.", "success")
                    return redirect(url_for("lookup"))
                else:
                    flash("Error updating PIN. Please try again.", "error")
            else:
                flash("User not found.", "error")

        return render_template("reset_pin.html", token=token)

    @app.route("/continue-monitoring/<token>")
    def continue_monitoring(token):
        """Reactivate a monitoring job from email link."""
        try:
            # Token contains job_id
            job_id = s.loads(
                token, salt="continue-monitoring", max_age=86400 * 7
            )  # 7 days valid
        except SignatureExpired:
            return render_template(
                "continue_monitoring.html",
                status="expired",
                message="This link has expired.",
            )
        except BadTimeSignature:
            return render_template(
                "continue_monitoring.html", status="invalid", message="Invalid link."
            )

        # Reactivate job
        if reactivate_job(job_id):
            job = get_job_by_id(job_id)
            return render_template(
                "continue_monitoring.html", status="success", job=job
            )
        else:
            return render_template(
                "continue_monitoring.html",
                status="error",
                message="Could not reactivate job. It may have been deleted.",
            )

    @app.route("/stop-monitoring/<token>")
    def stop_monitoring(token):
        """Stop monitoring (delete job) from email link."""
        try:
            # Token contains job_id, use distinct salt
            job_id = s.loads(token, salt="stop-monitoring", max_age=86400 * 7)
        except SignatureExpired:
            return render_template(
                "stop_monitoring.html",
                status="expired",
                message="This link has expired.",
            )
        except BadTimeSignature:
            return render_template(
                "stop_monitoring.html", status="invalid", message="Invalid link."
            )

        # Delete job
        # We need user_id for delete_monitoring_job(job_id, user_id)
        job = get_job_by_id(job_id)

        if job:
            # delete_monitoring_job requires user_id, which we have in job dict
            if delete_monitoring_job(job_id, job["user_id"]):
                return render_template(
                    "stop_monitoring.html", status="success", job=job
                )
            else:
                return render_template(
                    "stop_monitoring.html",
                    status="error",
                    message="Could not delete job.",
                )
        else:
            # Job might already be deleted
            return render_template(
                "stop_monitoring.html", status="success", message="Job already removed."
            )

    return app


def send_notification_email(app, job):
    """
    Send notification email with continue monitoring link.
    Must be called within app context or with app instance passed.
    """
    from flask_mail import Message
    from flask import url_for

    # We need to create tokens for the job_id
    s = URLSafeTimedSerializer(app.secret_key)

    # Continue token
    continue_token = s.dumps(job["job_id"], salt="continue-monitoring")

    # Stop token
    stop_token = s.dumps(job["job_id"], salt="stop-monitoring")

    # Generate URL (requires app context)
    # For local dev, let's try to infer or default
    base_url = os.environ.get("BASE_URL", "http://localhost:5000")
    continue_url = f"{base_url}/continue-monitoring/{continue_token}"
    stop_url = f"{base_url}/stop-monitoring/{stop_token}"

    resort_name = job["resort_name"]
    date = job["target_date"]
    resort_url = job["resort_url"]

    msg = Message(f"Parking Found: {resort_name} on {date}", recipients=[job["email"]])

    # Simple HTML body
    msg.html = f"""
    <h2>Parking Available!</h2>
    <p>We found parking at <strong>{resort_name}</strong> for <strong>{date}</strong>.</p>
    <p><a href="{resort_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Book Parking Now</a></p>
    <hr>
    <p>We have paused monitoring for this date to avoid spamming you.</p>
    
    <p><strong>Did you get the spot?</strong></p>
    <p><a href="{stop_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">I got Parking! Remove me</a></p>
    
    <p><strong>Still looking?</strong></p>
    <p><a href="{continue_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Continue Monitoring</a></p>
    """

    # Send
    # If called from daemon, 'mail' object needs to be attached to app
    mail = app.extensions.get("mail")
    if not mail:
        # Should have been initialized in create_app
        from flask_mail import Mail

        mail = Mail(app)

    mail.send(msg)
    return True


def send_no_reservation_email(app, user_email, resort_name, dates, resort_url=None):
    """
    Send email notifying user that selected dates do not require parking reservations.
    Uses Flask-Mail (same as send_notification_email) for consistent credential handling.
    """
    from flask_mail import Message

    base_url = os.environ.get("BASE_URL", "http://localhost:5000")

    # Format dates for display
    from datetime import datetime as dt

    formatted_dates = []
    for date in sorted(dates):
        try:
            date_obj = dt.strptime(date, "%Y-%m-%d")
            formatted_dates.append(date_obj.strftime("%A, %B %d, %Y"))
        except ValueError:
            formatted_dates.append(date)

    date_list_html = "".join(f"<li>{d}</li>" for d in formatted_dates)

    msg = Message(
        f"No Reservation Required: {resort_name}",
        recipients=[user_email],
    )

    msg.html = f"""
    <h2>No Parking Reservation Needed</h2>
    <p>Good news! The following date(s) at <strong>{resort_name}</strong> do <strong>NOT</strong> require a parking reservation:</p>
    <ul>{date_list_html}</ul>
    <p>These dates have been removed from your monitoring list since no action is needed.</p>
    {"<p><a href='" + resort_url + "' style='background-color: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;'>View Resort Page</a></p>" if resort_url else ""}
    <hr>
    <p>Want to monitor different dates? <a href="{base_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Set Up New Alerts</a></p>
    """

    mail = app.extensions.get("mail")
    if not mail:
        from flask_mail import Mail

        mail = Mail(app)

    mail.send(msg)
    return True
