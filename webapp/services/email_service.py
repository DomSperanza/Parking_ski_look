"""
Email Service

Handles email notifications and communications.
"""

import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Email configuration from environment
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")


def send_availability_notification(job_id, user_email, resort_name, date, resort_url=None):
    """
    Send email notification when parking becomes available.
    
    Args:
        job_id (int): Monitoring job ID
        user_email (str): Recipient email address
        resort_name (str): Name of the resort
        date (str): Available date in YYYY-MM-DD format
        resort_url (str, optional): URL to the reservation page
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("Email credentials not configured. Set SENDER_EMAIL and SENDER_PASSWORD environment variables.")
        return False
    
    # Format date for display
    try:
        from datetime import datetime
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%B %d, %Y')
    except ValueError:
        formatted_date = date
    
    # Create email content
    subject = f"Parking Available: {resort_name} on {formatted_date}"
    
    body = f"""Hello!

Parking is now available at {resort_name} for {formatted_date}.

"""
    
    if resort_url:
        body += f"Book your parking spot: {resort_url}\n\n"
    
    body += f"""This notification was sent by the Ski Parking Monitor.

Job ID: {job_id}
Date: {formatted_date}
Resort: {resort_name}

---
This is an automated notification. Please do not reply to this email.
"""
    
    # Create message
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = user_email
    message["Subject"] = subject
    
    message.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Email notification sent to {user_email} for job {job_id}")
        return True
        
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {user_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending email to {user_email}: {e}")
        return False


def send_test_email(user_email):
    """
    Send a test email to verify email configuration.
    
    Args:
        user_email (str): Recipient email address
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Ski Parking Monitor - Test Email"
    body = "This is a test email from the Ski Parking Monitor. Your email configuration is working correctly."
    
    message = MIMEText(body)
    message["From"] = SENDER_EMAIL
    message["To"] = user_email
    message["Subject"] = subject
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Test email sent to {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        return False
