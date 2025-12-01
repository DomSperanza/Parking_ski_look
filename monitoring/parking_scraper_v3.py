"""
Parking Scraper V3

Simple scraper to check parking availability by detecting background color on date elements.
Returns: "green" (available), "red" (unavailable), or "blank" (not found).
Uses undetected-chromedriver to bypass anti-bot measures.
"""

import sys
from pathlib import Path
import time
import re
import logging
import random
import json
from bs4 import BeautifulSoup

# Enforce undetected_chromedriver
try:
    import undetected_chromedriver as uc
    USE_UNDETECTED = True
except ImportError:
    # Fallback only if absolutely necessary, but warn heavily
    USE_UNDETECTED = False
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import pyvirtualdisplay for headless bypass
try:
    from pyvirtualdisplay import Display
    HAS_DISPLAY = True
except ImportError:
    HAS_DISPLAY = False

sys.path.append(str(Path(__file__).parent.parent))

from utils.date_converter import convert_to_aria_label
from config.database import (
    get_active_monitoring_jobs,
    update_job_last_checked,
    increment_job_success_count,
    create_notification,
    check_recent_notification,
    log_check_result,
    mark_job_notified
)
from webapp.app import send_notification_email
from flask import current_app

logger = logging.getLogger(__name__)

# Green color for available dates (from HTML examples)
# We'll check for the components (49, 200, 25) instead of strict string matching


def get_driver(headless=True):
    """
    Get a configured Chrome driver (undetected or standard).
    If running with pyvirtualdisplay (Display), we should run with headless=False 
    inside the virtual display to bypass detection.
    """
    # Check Chrome version for debugging
    import subprocess
    try:
        result = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
        logger.info(f"System Chrome version: {result.stdout.strip()}")
    except Exception as e:
        logger.warning(f"Could not determine Chrome version: {e}")

    # If we have a virtual display, we can run 'headed' inside it, which is stealthier
    if HAS_DISPLAY:
        # Override the headless argument if we have a display
        headless = False
        logger.info("Using pyvirtualdisplay: Running Chrome in HEADED mode (hidden in virtual display)")
    
    if USE_UNDETECTED:
        options = uc.ChromeOptions()
        
        # Do NOT set --headless argument manually for UC, use the headless arg in uc.Chrome()
        # options.add_argument("--headless=new") # Removed to let UC handle it
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Enable logging
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        # Profile persistence (helps with trust)
        profile_path = Path(__file__).parent.parent / "chrome_profile"
        options.add_argument(f"--user-data-dir={profile_path}")
        
        # Randomize window size slightly to look more natural
        width = random.randint(1024, 1920)
        height = random.randint(768, 1080)
        options.add_argument(f"--window-size={width},{height}")
        
        # Undetected chromedriver handles user-agent and automation flags automatically
        # Fix version mismatch by specifying version_main (User has Chrome 139)
        # headless=headless ensures correct patching for headless mode
        driver = uc.Chrome(
            options=options,
            headless=headless,
            use_subprocess=True,
        )
        return driver
    else:
        logger.warning("undetected-chromedriver not found! This is highly detectable.")
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Enable logging
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        # Anti-detection and headers
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Execute CDP commands to modify headers
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        
        return driver


def simulate_human_behavior(driver):
    """
    Simulate human-like behavior (scrolling, random pauses).
    """
    try:
        # Random small pause
        time.sleep(random.uniform(1.0, 3.0))
        
        # Random scroll
        scroll_amount = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
        
        # Scroll back up a bit sometimes
        if random.random() > 0.7:
            driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 200)});")
            time.sleep(random.uniform(0.5, 1.0))
            
    except Exception as e:
        logger.debug(f"Error simulating human behavior: {e}")


def is_green(style_attr):
    """
    Check if style attribute contains the green color (robustly).
    Matches: rgba(49, 200, 25, ...) ignoring spaces.
    """
    if not style_attr:
        return False
    
    # Normalize: remove spaces, lowercase
    style_norm = style_attr.lower().replace(" ", "")
    
    # Check for background-color presence
    if "background-color" not in style_norm:
        return False
    
    # Check for the RGB components of the green color
    # rgba(49, 200, 25, 0.2) -> we look for "49,200,25" or the full string
    if "49,200,25" in style_norm:
        return True
        
    # Fallback: check for rgb(49, 200, 25) just in case
    if "rgb(49,200,25)" in style_norm:
        return True
        
    return False


def scan_html_for_dates(html_content, date_list):
    """
    Parse HTML content with BeautifulSoup to check for date availability.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Check for blocked message
    if "Please try again" in soup.get_text() or "Access Denied" in soup.get_text():
        logger.error("BLOCKED: Detected anti-bot blocking message.")
        return {date: "blocked" for date in date_list}
        
    results = {}
    
    for date_str in date_list:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            aria_label = convert_to_aria_label(date_str)
        else:
            aria_label = date_str
            
        # Find element by aria-label
        # Note: BeautifulSoup select uses CSS selectors
        element = soup.select_one(f"[aria-label='{aria_label}']")
        
        if element:
            style_attr = element.get('style', '')
            logger.info(f"Found style for {date_str} (via HTML scan): {style_attr}")
            if is_green(style_attr):
                results[date_str] = "green"
            else:
                results[date_str] = "red"
        else:
            logger.warning(f"Element not found in HTML scan: {aria_label}")
            results[date_str] = "blank"
            
    return results


def check_date_availability(resort_url, date_str):
    """
    Check if a specific date has parking available.
    (Kept for compatibility, but check_multiple_dates is preferred)
    """
    return check_multiple_dates(resort_url, [date_str])[date_str]


def check_multiple_dates(resort_url, date_list):
    """
    Check availability for multiple dates by fetching the page source once and scanning it locally.
    """
    driver = None
    display = None
    results = {}
    
    try:
        # Start virtual display if available
        if HAS_DISPLAY:
            try:
                display = Display(visible=0, size=(1920, 1080))
                display.start()
                logger.info("Virtual display started")
            except Exception as e:
                logger.error(f"Failed to start virtual display (xvfb missing?): {e}")
                # Continue without display, get_driver will fallback to headless=True logic if needed
                # But wait, get_driver logic depends on HAS_DISPLAY constant, not runtime success
                # We'll need to handle that if get_driver uses HAS_DISPLAY but display failed.
                pass

        # If display failed to start, we should probably force headless=True in get_driver, 
        # but get_driver uses the global HAS_DISPLAY. 
        # For simplicity, if display.start() fails, we might crash or chrome might fail to open.
        # We'll assume user installs xvfb as requested.
        
        # Pass headless=True as default, but get_driver overrides it if HAS_DISPLAY is True
        driver = get_driver(headless=True) 
        
        driver.get(resort_url)
        
        # Simulate human behavior on load
        simulate_human_behavior(driver)
        
        # Wait for calendar to load
        # We wait for a generic amount of time or try to find at least one date to ensure content is there
        time.sleep(random.uniform(5.0, 10.0)) 
        
        # Attempt to wait for the first date to appear, just to ensure we don't snapshot blank page
        # But don't fail if it doesn't appear (could be scrolling issue), just proceed to snapshot
        try:
            first_date = date_list[0]
            if re.match(r'^\d{4}-\d{2}-\d{2}$', first_date):
                aria_label = convert_to_aria_label(first_date)
            else:
                aria_label = first_date
                
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"[aria-label='{aria_label}']")
                )
            )
        except Exception as e:
            logger.info(f"Wait for first date element timed out or failed, proceeding to snapshot anyway: {e}")

        timestamp = int(time.time())

        # Export Console Logs
        # (Disabled debug saving)
        # try:
        #     logs = driver.get_log('browser')
        #     log_filename = f"debug_console_{timestamp}.json"
        #     with open(log_filename, "w", encoding='utf-8') as f:
        #         json.dump(logs, f, indent=2)
        #     logger.info(f"Saved console logs to {log_filename}")
        # except Exception as e:
        #     logger.error(f"Failed to save console logs: {e}")

        # Export raw HTML
        # filename = f"debug_scan_{timestamp}.html"
        html_content = driver.page_source
        
        # with open(filename, "w", encoding='utf-8') as f:
        #     f.write(html_content)
        
        # logger.info(f"Saved raw HTML to {filename}")
        
        # Scan the local HTML file
        results = scan_html_for_dates(html_content, date_list)
        
        return results
        
    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        return {date_str: "blank" for date_str in date_list}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {date_str: "blank" for date_str in date_list}
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        if display:
            try:
                display.stop()
            except:
                pass


def check_monitoring_jobs():
    """
    Main function to check all active monitoring jobs.
    """
    jobs = get_active_monitoring_jobs()
    
    if not jobs:
        logger.info("No active jobs to check.")
        return
    
    # Group jobs by resort to minimize browser sessions
    resort_jobs = {}
    for job in jobs:
        resort_url = job['resort_url']
        if resort_url not in resort_jobs:
            resort_jobs[resort_url] = {
                'resort_id': job['resort_id'],
                'resort_name': job['resort_name'],
                'dates': set(),
                'jobs': []
            }
        
        resort_jobs[resort_url]['dates'].add(job['target_date'])
        resort_jobs[resort_url]['jobs'].append(job)
    
    # Process each resort
    for resort_url, data in resort_jobs.items():
        resort_name = data['resort_name']
        resort_id = data['resort_id']
        dates = list(data['dates'])
        
        logger.info(f"Checking {resort_name} for dates: {dates}")
        
        # Random delay between resorts
        time.sleep(random.uniform(3.0, 8.0))
        
        start_time = time.time()
        results = check_multiple_dates(resort_url, dates)
        duration = int((time.time() - start_time) * 1000)
        
        # Log check result
        status = "success" if any(r != "blank" and r != "blocked" for r in results.values()) else "failed"
        availability_found = any(r == "green" for r in results.values())
        log_check_result(resort_id, status, duration, availability_found=availability_found)
        
        # Process results for each job
        for job in data['jobs']:
            job_id = job['job_id']
            target_date = job['target_date']
            result = results.get(target_date, "blank")
            
            # Update last checked
            update_job_last_checked(job_id)
            
            if result == "green":
                logger.info(f"FOUND AVAILABILITY! {resort_name} on {target_date}")
                increment_job_success_count(job_id)
                
                # Check if we should send notification (debounce)
                # We rely on the status toggle (active -> notified) to prevent spam.
                # If the job is here (active), the user wants to be notified.
                create_notification(
                    job_id, 
                    job['user_id'], 
                    resort_name, 
                    target_date
                )
                
                try:
                    logger.info(f"Attempting to send email to {job['email']}")
                    sent = send_notification_email(current_app._get_current_object(), job)
                    if sent:
                        logger.info(f"Notification sent to {job['email']}")
                        mark_job_notified(job_id)
                    else:
                        logger.error(f"send_notification_email returned False for {job['email']}")
                    
                except Exception as e:
                    logger.error(f"Failed to send email to {job['email']}: {e}", exc_info=True)
            elif result == "red":
                logger.debug(f"Not available: {resort_name} on {target_date}")
            elif result == "blocked":
                logger.warning(f"Blocked by anti-bot protection for {resort_name}")
            else:
                logger.warning(f"Could not check status: {resort_name} on {target_date}")
