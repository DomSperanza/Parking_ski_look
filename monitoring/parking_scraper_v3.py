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

# Try to import undetected_chromedriver, fallback to standard selenium if not installed
try:
    import undetected_chromedriver as uc
    USE_UNDETECTED = True
except ImportError:
    USE_UNDETECTED = False
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

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
AVAILABLE_GREEN = "rgba(49, 200, 25, 0.2)"


def get_driver(headless=True):
    """
    Get a configured Chrome driver (undetected or standard).
    """
    if USE_UNDETECTED:
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Undetected chromedriver handles user-agent and automation flags automatically
        driver = uc.Chrome(options=options)
        return driver
    else:
        logger.warning("undetected-chromedriver not found, using standard Selenium")
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
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


def check_date_availability(resort_url, date_str):
    """
    Check if a specific date has parking available.
    """
    driver = None
    
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            aria_label = convert_to_aria_label(date_str)
        else:
            aria_label = date_str
        
        driver = get_driver()
        driver.get(resort_url)
        
        # Wait for calendar to load
        wait = WebDriverWait(driver, 30)
        time.sleep(8)
        
        try:
            date_element = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"[aria-label='{aria_label}']")
                )
            )
            wait.until(EC.visibility_of(date_element))
            time.sleep(2)
        except TimeoutException:
            return "blank"
        
        style_attr = date_element.get_attribute("style")
        
        if style_attr and "background-color" in style_attr.lower():
            if AVAILABLE_GREEN in style_attr:
                return "green"
            else:
                return "red"
        else:
            return "red"
        
    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        return "blank"
    except Exception as e:
        logger.error(f"Error checking date: {e}")
        return "blank"
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def check_multiple_dates(resort_url, date_list):
    """
    Check availability for multiple dates in a single browser session.
    """
    driver = None
    results = {}
    
    try:
        driver = get_driver()
        driver.get(resort_url)
        
        # Wait for calendar to load
        wait = WebDriverWait(driver, 30)
        time.sleep(8)
        
        for date_str in date_list:
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                aria_label = convert_to_aria_label(date_str)
            else:
                aria_label = date_str
            
            try:
                try:
                    date_element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, f"[aria-label='{aria_label}']")
                        )
                    )
                except TimeoutException:
                    results[date_str] = "blank"
                    continue
                
                style_attr = date_element.get_attribute("style")
                
                if style_attr and "background-color" in style_attr.lower():
                    if AVAILABLE_GREEN in style_attr:
                        results[date_str] = "green"
                    else:
                        results[date_str] = "red"
                else:
                    results[date_str] = "red"
                    
            except Exception as e:
                results[date_str] = "blank"
        
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
        
        start_time = time.time()
        results = check_multiple_dates(resort_url, dates)
        duration = int((time.time() - start_time) * 1000)
        
        # Log check result
        status = "success" if any(r != "blank" for r in results.values()) else "failed"
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
                if not check_recent_notification(job_id):
                    create_notification(
                        job_id, 
                        job['user_id'], 
                        resort_name, 
                        target_date
                    )
                    
                    try:
                        send_notification_email(current_app._get_current_object(), job)
                        logger.info(f"Notification sent to {job['email']}")
                        mark_job_notified(job_id)
                        
                    except Exception as e:
                        logger.error(f"Failed to send email to {job['email']}: {e}")
            elif result == "red":
                logger.debug(f"Not available: {resort_name} on {target_date}")
            else:
                logger.warning(f"Could not check status: {resort_name} on {target_date}")
