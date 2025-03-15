import threading
import smtplib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from playsound import playsound
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ----------------- Configuration -----------------

# List of resort URLs that use the same parking software.
URLS = [
    "https://reservenski.parkbrightonresort.com/select-parking",
    "https://reservenski.parksolitude.com/select-parking",  # Replace with the actual URL for resort 2.
    # Add additional URLs as needed.
]

# Monitoring settings.
CHECK_INTERVAL = 10  # Seconds to wait between checks/refreshed.
# List of target appointments (aria-label values) to check on each site.
TARGET_APPOINTMENTS = [
    "Sunday, March 16, 2025"
]
# When a date is not available, its background color is this.
UNAVAILABLE_COLOR = "rgba(247, 205, 212, 1)"
AVAILABLE_COLOR = "rgba(49, 200, 25, 0.2)"
# Path to your alert sound file
ALERT_SOUND_PATH = "beep.wav"  # Ensure this file is in the same directory as your script

# Email settings.
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS").split(",")

# ----------------- Email Notification -----------------

def send_email_notification(data=None, receiver_emails=None):
    """Send an email notification with the provided data."""
    subject = "Subject: Appointment Available!\n\n"
    body = "An appointment has become available. Details:\n" + str(data)
    message = subject + body
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            for receiver_email in receiver_emails:
                server.sendmail(SENDER_EMAIL, receiver_email, message)
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

# ----------------- Resort Monitoring Function -----------------

def check_resort(url):
    """
    Opens a dedicated webdriver for the given resort URL and, in a loop,
    checks each target appointment for its availability based on its background color.
    If a target appointment becomes available, an email notification is sent.
    Once an email is sent, further notifications are suppressed until a check
    shows the appointment is no longer available.
    """
    print(f"Starting monitoring for: {url}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get(url)
    
    # Initialize state tracking for each appointment.
    notification_sent = {appointment: False for appointment in TARGET_APPOINTMENTS}
    availability_counter = {appointment: 0 for appointment in TARGET_APPOINTMENTS}
    
    try:
        while True:
            for appointment in TARGET_APPOINTMENTS:
                print(f"\nResort: {url} -- Checking appointment: {appointment}")
                wait = WebDriverWait(driver, 10)
                try:
                    date_element = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, f"[aria-label='{appointment}']")
                        )
                    )
                except Exception as e:
                    print(f"Resort: {url} -- Could not locate element for '{appointment}': {e}")
                    continue
                
                # Allow an extra second for the dynamic content to settle.
                time.sleep(1)
                
                color = date_element.value_of_css_property("background-color")
                print(f"Resort: {url} -- Color for '{appointment}' is {color}")
                
                # Check if the appointment is available.
                if color.strip() == AVAILABLE_COLOR:
                    # Appointment is available.
                    if not notification_sent[appointment]:
                        print(f"Resort: {url} -- 🚨 {appointment} is available! Sending notification.")
                        send_email_notification(
                            data=f"Resort: {url}\nAppointment: {appointment}\nColor: {color}",
                            receiver_emails=RECEIVER_EMAILS
                        )
                        notification_sent[appointment] = True
                        availability_counter[appointment] = 1
                    else:
                        availability_counter[appointment] += 1
                        print(f"Resort: {url} -- {appointment} remains available. (Count = {availability_counter[appointment]}) -- No additional email sent.")
                else:
                    # Appointment is not available: reset the notification flag.
                    if notification_sent[appointment]:
                        print(f"Resort: {url} -- {appointment} is now NOT available. Resetting notification flag.")
                    notification_sent[appointment] = False
                    availability_counter[appointment] = 0
            
            print(f"Resort: {url} -- Waiting {CHECK_INTERVAL} seconds before refreshing...")
            time.sleep(CHECK_INTERVAL)
            driver.refresh()
    except Exception as e:
        print(f"Exception occurred while monitoring resort {url}: {e}")
    finally:
        driver.quit()

# ----------------- Main Function -----------------

def main():
    threads = []
    # Start a separate thread for each resort URL.
    for url in URLS:
        t = threading.Thread(target=check_resort, args=(url,))
        t.daemon = True  # Threads will exit when the main program exits.
        t.start()
        threads.append(t)
    
    # Keep the main thread alive.
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Monitoring stopped by user.")

if __name__ == "__main__":
    main() 