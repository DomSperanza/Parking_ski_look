"""
Parking Scraper V3

Simple scraper to check parking availability by detecting background color on date elements.
Returns: "green" (available), "red" (unavailable), or "blank" (not found).
Uses undetected-chromedriver to bypass anti-bot measures.
"""

import sys
import os
import subprocess
from pathlib import Path
import time
import re
import logging
import random
import json
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

try:
    import undetected_chromedriver as uc

    # Force disable UC for stability - user requested standard Selenium default
    UC_AVAILABLE = False
except ImportError:
    UC_AVAILABLE = False

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import pyvirtualdisplay for headless bypass
# Try to import pyvirtualdisplay for headless bypass
# REMOVED: pyvirtualdisplay dependency - switching to native headless=new

sys.path.append(str(Path(__file__).parent.parent))

from utils.date_converter import convert_to_aria_label
from config.database import (
    get_active_monitoring_jobs,
    update_job_last_checked,
    increment_job_success_count,
    create_notification,
    check_recent_notification,
    log_check_result,
    mark_job_notified,
)
from webapp.app import send_notification_email
from flask import current_app

logger = logging.getLogger(__name__)

# Green color for available dates (from HTML examples)
# We'll check for the components (49, 200, 25) instead of strict string matching

# Session management - keep drivers alive per resort
_resort_drivers = {}  # {resort_url: driver}
_driver_use_count = {}  # Track how many times each driver has been used
_MAX_DRIVER_USES = 3  # Reduced to prevent fingerprint tracking (was 10)
_MAX_CONCURRENT_DRIVERS = 1  # Limit concurrent browsers to save memory (1.9GB VPS)


def _get_chrome_version_main():
    """
    Get the major version number of the installed Chrome (e.g. 143).
    Used so undetected-chromedriver uses a matching ChromeDriver.
    Returns None if detection fails.
    """
    try:
        result = subprocess.run(
            ["google-chrome", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        # e.g. "Google Chrome 143.0.7499.146" or "Chromium 143.0.0.0"
        match = re.search(r"(?:Chrome|Chromium)\s+(\d+)\.", result.stdout.strip())
        if match:
            return int(match.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug(f"Could not get Chrome major version: {e}")
    return None


def _build_chrome_options(profile_dir, for_undetected_chromedriver=False):
    """
    Build Chrome options with all necessary flags and preferences.

    Args:
        profile_dir: Path to Chrome profile directory
        for_undetected_chromedriver: If True, exclude experimental options that UC doesn't support

    Returns:
        Configured Chrome Options object
    """
    chrome_options = Options()

    # Critical flags for Docker environment
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Only use display :99 if running in Docker/headless environment
    if os.path.exists("/tmp/.X99-lock") or os.environ.get("DISPLAY") == ":99":
        chrome_options.add_argument("--display=:99")

    # Memory-saving flags for low-RAM VPS
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    # chrome_options.add_argument(
    #    "--disable-features=TranslateUI,IsolateOrigins,site-per-process"
    # )
    # chrome_options.add_argument("--disable-ipc-flooding-protection")
    # chrome_options.add_argument("--memory-pressure-off")

    # Enhanced stealth options
    # chrome_options.add_argument("--disable-blink-features=AutomationControlled") # Handled by uc
    # chrome_options.add_argument("--disable-plugins-discovery")
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--disable-web-security") # HIGHLY DETECTABLE
    # chrome_options.add_argument("--disable-features=VizDisplayCompositor")

    # Use persistent Chrome profile to maintain cookies/session
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--profile-directory=Default")

    # Disable profile picker and first run
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-infobars")

    # Exclude automation switches - only for standard Selenium
    # undetected-chromedriver handles these internally
    if not for_undetected_chromedriver:
        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)

    # Set realistic preferences
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.images": 2,  # Disable images to save memory
    }
    chrome_options.add_experimental_option("prefs", prefs)

    return chrome_options


def get_driver(headless=True, profile_name="default"):
    """
    Get a configured Chrome driver with enhanced stealth.
    Falls back to standard Selenium if undetected-chromedriver fails.

    Args:
        headless: Whether to run in headless mode (not currently used)
        profile_name: Unique profile name to avoid lock conflicts
    """
    import hashlib
    import shutil

    version_main = _get_chrome_version_main()
    if version_main:
        logger.info(f"System Chrome major version: {version_main}")
    else:
        logger.warning("Could not determine System Chrome version")

    # Force kill any zombie chrome processes to free resources
    # ONLY run this inside Docker to avoid killing user's personal browser
    if os.path.exists("/app"):
        try:
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
            subprocess.run(["pkill", "-f", "chromedriver"], capture_output=True)
        except:
            pass

    # Determine base profile directory based on environment
    if os.path.exists("/app"):
        # Docker environment
        base_profile_dir = "/app/chrome_profile"
    else:
        # Local environment - use project directory
        project_root = Path(__file__).parent.parent
        base_profile_dir = str(project_root / "chrome_profile")

    # Create unique profile directory per session to avoid locks
    # Use hash of profile_name to keep it short
    profile_hash = hashlib.md5(profile_name.encode()).hexdigest()[:8]
    profile_dir = os.path.join(base_profile_dir, profile_hash)

    # Create profile directory if it doesn't exist
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Using Chrome profile directory: {profile_dir}")

    try:
        # Try undetected-chromedriver first if available
        if UC_AVAILABLE:
            logger.info("Creating Chrome driver with undetected-chromedriver")

            # Helper to create driver with retries
            def create_uc_driver():
                uc_options = _build_chrome_options(
                    profile_dir, for_undetected_chromedriver=True
                )
                return uc.Chrome(
                    options=uc_options,
                    user_data_dir=profile_dir,
                    version_main=version_main,  # Match installed Chrome
                )

            try:
                driver = create_uc_driver()
                logger.info(
                    "Chrome driver created successfully with undetected-chromedriver"
                )
                return driver
            except Exception as uc_error:
                logger.warning(
                    f"undetected-chromedriver failed first attempt: {uc_error}"
                )
                logger.info(
                    "Falling back to standard Selenium directly to avoid crash loops..."
                )
                # Fallback to standard Selenium below

        # Fallback to standard Selenium with all options including experimental ones
        logger.info("Creating Chrome driver with standard Selenium")
        chrome_options = _build_chrome_options(
            profile_dir, for_undetected_chromedriver=False
        )

        # Explicitly requesting the version we detected
        driver_path = None
        try:
            # Try new API (webdriver-manager 4.0+)
            if version_main:
                logger.info(
                    f"Installing ChromeDriver version matching Chrome {version_main}..."
                )
                driver_path = ChromeDriverManager(
                    driver_version=str(version_main)
                ).install()
            else:
                logger.info(
                    "Installing latest ChromeDriver (version detection failed)..."
                )
                driver_path = ChromeDriverManager().install()
        except TypeError:
            # Fallback to old API (webdriver-manager 3.x)
            logger.info("Falling back to legacy ChromeDriverManager API")
            if version_main:
                driver_path = ChromeDriverManager(version=str(version_main)).install()
            else:
                driver_path = ChromeDriverManager().install()

        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)

        # Custom stealth scripts removed to avoid conflicting with actual OS environment
        # and triggering advanced bot detection (e.g. Cloudflare) that checks for
        # OS/Browser mismatches (Linux container vs Win32 override).
        # unrecognized-chromedriver handles the critical navigator.webdriver property natively.

        logger.info("Chrome driver created successfully")
        return driver

    except Exception as e:
        logger.error(f"Failed to create Chrome driver: {e}")
        raise


def simulate_human_behavior(driver):
    """
    Simulate realistic human-like behavior (scrolling, pauses, mouse movements).
    """
    try:
        from selenium.webdriver.common.action_chains import ActionChains

        actions = ActionChains(driver)

        # Initial pause - like a human reading the page
        time.sleep(random.uniform(2.0, 4.0))

        # Smooth scrolling down (like reading the page)
        scroll_steps = random.randint(3, 6)
        for _ in range(scroll_steps):
            scroll_amount = random.randint(150, 400)
            # Smooth scroll using JavaScript
            driver.execute_script(
                f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}});"
            )
            time.sleep(random.uniform(0.8, 2.0))  # Pause between scrolls like reading

        # Sometimes scroll back up a bit (like re-reading something)
        if random.random() > 0.6:
            back_scroll = random.randint(100, 300)
            driver.execute_script(
                f"window.scrollBy({{top: -{back_scroll}, behavior: 'smooth'}});"
            )
            time.sleep(random.uniform(1.0, 2.5))

        # Random mouse movement simulation (hover over elements)
        try:
            # Try to find some interactive elements to hover over
            buttons = driver.find_elements(By.TAG_NAME, "button")
            links = driver.find_elements(By.TAG_NAME, "a")
            all_elements = buttons + links

            if all_elements and random.random() > 0.4:
                element = random.choice(all_elements[:10])  # Pick from first 10
                try:
                    # Move to element smoothly
                    driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                        element,
                    )
                    time.sleep(random.uniform(0.3, 0.8))
                    actions.move_to_element(element).pause(
                        random.uniform(0.2, 0.5)
                    ).perform()
                    time.sleep(random.uniform(0.5, 1.2))
                except:
                    pass
        except:
            pass

        # Sometimes move mouse to a random position (like moving cursor around)
        if random.random() > 0.7:
            try:
                # Move to random position on page
                x_offset = random.randint(-200, 200)
                y_offset = random.randint(-200, 200)
                actions.move_by_offset(x_offset, y_offset).perform()
                time.sleep(random.uniform(0.3, 0.8))
            except:
                pass

        # Final pause before checking dates (like looking at calendar)
        time.sleep(random.uniform(1.5, 3.0))

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


def get_console_logs(driver):
    """
    Get browser console logs for debugging.
    """
    try:
        logs = driver.get_log("browser")
        return [log["message"] for log in logs]
    except Exception as e:
        logger.debug(f"Could not retrieve console logs: {e}")
        return []


def handle_cloudflare_challenge(driver):
    """
    Attempt to handle Cloudflare Turnstile challenge by clicking the checkbox.
    """
    try:
        # Wait for iframe to be available
        time.sleep(3)

        # Get console logs to debug why iframe might be missing
        try:
            logs = driver.get_log("browser")
            for log in logs:
                logger.debug(f"Browser Log: {log}")
        except:
            pass

        # Check for specific failure message
        page_source = driver.page_source
        if "Verification failed" in page_source:
            logger.warning(
                "Found 'Verification failed' message on page - Turnstile likely failed to load or was rejected immediately."
            )

        # Find all iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        logger.info(f"Found {len(iframes)} iframes on page")

        # Check for the widget specifically
        try:
            widget = driver.find_element(By.CLASS_NAME, "turnstile-widget")
            logger.info(
                f"Found turnstile-widget. Display: {widget.value_of_css_property('display')}"
            )
        except:
            logger.info("Could not find .turnstile-widget element")

        if len(iframes) == 0:
            logger.info("No iframes found for challenge handling")

        challenge_iframe = None
        for iframe in iframes:
            try:
                src = iframe.get_attribute("src")
                if src and ("cloudflare" in src or "turnstile" in src):
                    challenge_iframe = iframe
                    logger.info("Found Cloudflare/Turnstile iframe")
                    break

                # Also check by title or ID potentially
                title = iframe.get_attribute("title")
                if title and "challenge" in title.lower():
                    challenge_iframe = iframe
                    logger.info("Found iframe with challenge title")
                    break
            except:
                continue

        if challenge_iframe:
            # Switch to iframe
            driver.switch_to.frame(challenge_iframe)
            logger.info("Switched to challenge iframe")
            time.sleep(random.uniform(1.0, 2.0))

            # Try to find the checkbox/button
            # Turnstile usually has a checkbox in a shadow DOM or directly
            try:
                # Common selector for Turnstile checkbox
                checkbox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "input[type='checkbox'], .unbranded")
                    )
                )
                if checkbox:
                    logger.info("Found challenge checkbox, attempting to click...")
                    time.sleep(random.uniform(0.5, 1.5))
                    checkbox.click()
                    logger.info("Clicked challenge checkbox")

                    # Wait for resolution
                    time.sleep(random.uniform(2.0, 4.0))
            except Exception as e:
                logger.warning(f"Could not find/click specific checkbox in iframe: {e}")

            # Switch back to main content
            driver.switch_to.default_content()

            # Wait for reload/redirect
            time.sleep(5)

        else:
            logger.info(
                "No specific Cloudflare iframe found, checking for button in main frame"
            )
            # Sometimes it's not in an iframe or we missed it
            # Look for "Verify you are human" button
            try:
                button = driver.find_element(
                    By.XPATH,
                    "//button[contains(text(), 'Verify') or contains(text(), 'Human')]",
                )
                if button:
                    button.click()
                    logger.info("Clicked potential verify button")
            except:
                pass

    except Exception as e:
        logger.error(f"Error handling Cloudflare challenge: {e}")
        try:
            driver.switch_to.default_content()
        except:
            pass


def scan_html_for_dates(html_content, date_list, console_logs=None):
    """
    Parse HTML content with BeautifulSoup to check for date availability.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    page_text = soup.get_text()

    # Check for blocked message in HTML
    blocking_indicators = [
        "Please try again",
        "Access Denied",
        "forbidden",
        "cloudflare",
        "challenge",
        "captcha",
        "rate limit",
        "too many requests",
    ]

    # CORS errors are normal browser behavior, not blocking
    cors_indicators = ["cors", "access-control-allow-origin"]

    blocking_found = False
    blocking_details = []

    # Check HTML content
    for indicator in blocking_indicators:
        if indicator.lower() in page_text.lower():
            blocking_found = True
            blocking_details.append(f"HTML contains: '{indicator}'")

    # Check console logs if provided
    if console_logs:
        console_text = " ".join(console_logs).lower()
        # Filter out CORS errors (normal browser behavior)
        non_cors_logs = [
            log
            for log in console_logs
            if not any(cors_ind in log.lower() for cors_ind in cors_indicators)
        ]
        non_cors_text = " ".join(non_cors_logs).lower()

        for indicator in blocking_indicators:
            if indicator.lower() in non_cors_text:
                blocking_found = True
                blocking_details.append(f"Console contains: '{indicator}'")
                # Log relevant console errors
                relevant_logs = [
                    log for log in non_cors_logs if indicator.lower() in log.lower()
                ]
                if relevant_logs:
                    logger.error(f"Console blocking indicators: {relevant_logs[:3]}")

    if blocking_found:
        error_msg = f"BLOCKED: Detected anti-bot blocking. Details: {'; '.join(blocking_details)}"
        logger.error(error_msg)
        return {date: "blocked" for date in date_list}

    results = {}

    for date_str in date_list:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            aria_label = convert_to_aria_label(date_str)
        else:
            aria_label = date_str

        # Find element by aria-label
        # Note: BeautifulSoup select uses CSS selectors
        element = soup.select_one(f"[aria-label='{aria_label}']")

        if element:
            style_attr = element.get("style", "")
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


def cleanup_driver(resort_url, clear_profile=False):
    """
    Clean up driver for a specific resort (e.g., when blocked).
    If clear_profile is True, also remove the profile directory to start fresh.
    """
    global _resort_drivers, _driver_use_count

    # Check if we are using a shared driver
    SHARED_KEY = "shared_driver"
    if SHARED_KEY in _resort_drivers and resort_url != SHARED_KEY:
        # If we are using a shared driver, don't quit it when cleaning up a specific resort
        # The shared driver checks its own health in get_or_create_driver
        logger.debug(f"Skipping driver cleanup for {resort_url} (using shared driver)")
        return

    if resort_url in _resort_drivers:
        try:
            _resort_drivers[resort_url].quit()
        except:
            pass
        del _resort_drivers[resort_url]
        if resort_url in _driver_use_count:
            del _driver_use_count[resort_url]
        logger.info(f"Cleaned up driver for {resort_url}")

    # Clear profile directory if blocked to prevent fingerprint tracking
    if clear_profile:
        import shutil

        if os.path.exists("/app"):
            base_profile_dir = "/app/chrome_profile"
        else:
            project_root = Path(__file__).parent.parent
            base_profile_dir = str(project_root / "chrome_profile")

        import hashlib

        profile_hash = hashlib.md5(resort_url.encode()).hexdigest()[:8]
        profile_dir = os.path.join(base_profile_dir, profile_hash)

        if os.path.exists(profile_dir):
            try:
                # Try to remove with retries
                for i in range(3):
                    try:
                        shutil.rmtree(profile_dir, ignore_errors=False)
                        logger.info(
                            f"Cleared profile directory for {resort_url} to prevent fingerprint tracking"
                        )
                        break
                    except OSError:
                        if i == 2:
                            # Final attempt with ignore_errors
                            shutil.rmtree(profile_dir, ignore_errors=True)
                            logger.warning(
                                f"Force removed profile directory for {resort_url} (some files might remain)"
                            )
                        else:
                            time.sleep(1)
            except Exception as e:
                logger.warning(f"Could not clear profile directory: {e}")


def cleanup_all_drivers():
    """
    Clean up all active drivers (e.g., on shutdown).
    """
    global _resort_drivers, _driver_use_count
    for resort_url, driver in list(_resort_drivers.items()):
        try:
            driver.quit()
        except:
            pass
    _resort_drivers.clear()
    _driver_use_count.clear()
    logger.info("Cleaned up all drivers")


def get_or_create_driver(resort_url):
    """
    Get existing driver for resort or create a new one.
    Returns driver and whether it was newly created.
    """
    global _resort_drivers, _driver_use_count

    # SINGLE PERSISTENT DRIVER IMPLEMENTATION
    # Use a fixed key for the shared driver
    SHARED_KEY = "shared_driver"

    # Check if we have an existing shared driver
    if SHARED_KEY in _resort_drivers:
        driver = _resort_drivers[SHARED_KEY]

        # Check if driver is still alive
        try:
            # Try to get current URL to verify driver is responsive
            _ = driver.current_url
            # We don't limit uses anymore, we want it to persist as long as possible
            return driver, False
        except:
            # Driver is dead, remove it
            logger.warning("Shared driver is no longer responsive, recreating...")
            try:
                driver.quit()
            except:
                pass
            del _resort_drivers[SHARED_KEY]

    # If we get here, we need to create a new driver
    logger.info(
        f"Creating NEW shared browser session (will be reused for {resort_url})"
    )

    # Use a RANDOM profile name for each new driver instance
    # This ensures that if we kill the driver (e.g. on blocking), we get a fresh profile next time
    import uuid

    random_profile = f"profile_{uuid.uuid4().hex[:8]}"

    driver = get_driver(headless=False, profile_name=random_profile)
    _resort_drivers[SHARED_KEY] = driver
    return driver, True


def check_multiple_dates(resort_url, date_list, refresh_only=False):
    """
    Check availability for multiple dates by fetching the page source once and scanning it locally.
    Includes robust retry logic to handle driver crashes (e.g. connection refused).
    """
    max_retries = 2

    for attempt in range(max_retries):
        driver = None
        is_new_session = False

        try:
            # Get or create driver for this resort
            driver, is_new_session = get_or_create_driver(resort_url)

            # Always navigate fresh (refresh was causing redirects/blocking)
            # But keep browser session alive between navigations
            logger.info(
                f"Navigating to {resort_url} (Attempt {attempt+1}/{max_retries})"
            )
            driver.get(resort_url)

            # Wait for page to start loading (like a real browser)
            # Extra time on new session to pass challenge pages - increased for Cloudflare
            if is_new_session:
                logger.info("New session - waiting longer for any challenge pages")
                # Longer wait for Cloudflare Turnstile to complete
                time.sleep(random.uniform(10.0, 15.0))
            else:
                time.sleep(random.uniform(3.0, 5.0))

            # Check for Cloudflare challenge and wait if present
            try:
                # Look for common Cloudflare challenge indicators
                challenge_indicators = [
                    "challenges.cloudflare.com",
                    "cf-browser-verification",
                    "cf-challenge",
                    "turnstile",
                ]
                page_source = driver.page_source.lower()
                if any(indicator in page_source for indicator in challenge_indicators):
                    logger.info(
                        "Detected Cloudflare challenge, attempting to handle..."
                    )
                    handle_cloudflare_challenge(driver)
            except Exception as e:
                logger.warning(f"Error checking/handling Cloudflare challenge: {e}")

            # Check if we were redirected to a blocking page
            try:
                current_url = driver.current_url
                page_title = driver.title.lower()

                if current_url != resort_url:
                    logger.warning(f"Redirected from {resort_url} to {current_url}")

                if any(
                    indicator in page_title
                    for indicator in [
                        "blocked",
                        "access denied",
                        "challenge",
                        "captcha",
                    ]
                ):
                    logger.error(
                        f"BLOCKED: Page title indicates blocking: {page_title}"
                    )
                    return {date_str: "blocked" for date_str in date_list}
            except Exception as e:
                # If we can't even get URL/Title, something is wrong with driver
                raise WebDriverException(f"Failed to check URL/Title: {e}")

            # Wait for page to fully load (like a human waiting for content)
            time.sleep(random.uniform(3.0, 5.0))

            # Simulate human behavior - browsing the page naturally
            simulate_human_behavior(driver)

            # Additional pause - like looking at the calendar
            time.sleep(random.uniform(2.0, 4.0))

            # Attempt to wait for the first date to appear, just to ensure we don't snapshot blank page
            # But don't fail if it doesn't appear (could be scrolling issue), just proceed to snapshot
            try:
                first_date = date_list[0]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", first_date):
                    aria_label = convert_to_aria_label(first_date)
                else:
                    aria_label = first_date

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, f"[aria-label='{aria_label}']")
                    )
                )
            except Exception as e:
                logger.info(
                    f"Wait for first date element timed out or failed, proceeding to snapshot anyway: {e}"
                )

            # Get console logs before closing
            console_logs = get_console_logs(driver)

            # Export raw HTML
            html_content = driver.page_source

            # Scan the local HTML file with console logs
            results = scan_html_for_dates(
                html_content, date_list, console_logs=console_logs
            )

            return results

        except (WebDriverException, Exception) as e:
            # Check if this is a connection/driver error that warrants a retry
            error_str = str(e).lower()
            is_connection_error = any(
                x in error_str
                for x in [
                    "connection refused",
                    "connection reset",
                    "closed",
                    "not reachable",
                    "session",
                    "disconnected",
                    "max retries exceeded",
                    "broken pipe",
                ]
            )

            if is_connection_error or isinstance(e, WebDriverException):
                logger.warning(f"Driver/Connection error on attempt {attempt+1}: {e}")

                # CRITICAL: Clean up the broken driver so next attempt gets a fresh one
                cleanup_driver(resort_url, clear_profile=False)

                if attempt < max_retries - 1:
                    logger.info(f"Retrying check for {resort_url} in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    logger.error(f"Max retries reached for {resort_url}. Giving up.")
            else:
                # For non-driver errors (e.g. logic bugs), logging and returning is safer than retrying loops
                logger.error(
                    f"Unexpected error checking {resort_url}: {e}", exc_info=True
                )

            return {date_str: "blank" for date_str in date_list}

    return {date_str: "blank" for date_str in date_list}


def check_monitoring_jobs():
    """
    Main function to check all active monitoring jobs.
    Returns True if any resort was blocked, False otherwise.
    """
    jobs = get_active_monitoring_jobs()

    if not jobs:
        logger.info("No active jobs to check.")
        return False

    # Group jobs by resort to minimize browser sessions
    resort_jobs = {}
    for job in jobs:
        resort_url = job["resort_url"]
        if resort_url not in resort_jobs:
            resort_jobs[resort_url] = {
                "resort_id": job["resort_id"],
                "resort_name": job["resort_name"],
                "dates": set(),
                "jobs": [],
            }

        resort_jobs[resort_url]["dates"].add(job["target_date"])
        resort_jobs[resort_url]["jobs"].append(job)

    # Track if any resort was blocked
    was_blocked = False

    # Process each resort
    for resort_url, data in resort_jobs.items():
        resort_name = data["resort_name"]
        resort_id = data["resort_id"]
        dates = list(data["dates"])

        logger.info(f"Checking {resort_name} for dates: {dates}")

        # Longer random delay between resorts to appear more human
        time.sleep(random.uniform(5.0, 12.0))

        start_time = time.time()
        # Navigate fresh but keep browser session alive
        results = check_multiple_dates(resort_url, dates, refresh_only=False)
        duration = int((time.time() - start_time) * 1000)

        if any(r == "blocked" for r in results.values()):
            was_blocked = True
            # Clean up driver and profile for this resort when blocked to prevent fingerprint tracking
            cleanup_driver(resort_url, clear_profile=True)

        # Log check result
        status = (
            "success"
            if any(r != "blank" and r != "blocked" for r in results.values())
            else "failed"
        )
        availability_found = any(r == "green" for r in results.values())
        log_check_result(
            resort_id, status, duration, availability_found=availability_found
        )

        # Process results for each job
        for job in data["jobs"]:
            job_id = job["job_id"]
            target_date = job["target_date"]
            result = results.get(target_date, "blank")

            # Update last checked
            update_job_last_checked(job_id)

            if result == "green":
                logger.info(f"FOUND AVAILABILITY! {resort_name} on {target_date}")
                increment_job_success_count(job_id)

                # Check if we should send notification (debounce)
                # We rely on the status toggle (active -> notified) to prevent spam.
                # If the job is here (active), the user wants to be notified.
                create_notification(job_id, job["user_id"], resort_name, target_date)

                try:
                    logger.info(f"Attempting to send email to {job['email']}")
                    sent = send_notification_email(
                        current_app._get_current_object(), job
                    )
                    if sent:
                        logger.info(f"Notification sent to {job['email']}")
                        mark_job_notified(job_id)
                    else:
                        logger.error(
                            f"send_notification_email returned False for {job['email']}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to send email to {job['email']}: {e}", exc_info=True
                    )
            elif result == "red":
                logger.debug(f"Not available: {resort_name} on {target_date}")
            elif result == "blocked":
                logger.warning(f"Blocked by anti-bot protection for {resort_name}")
            else:
                logger.warning(
                    f"Could not check status: {resort_name} on {target_date}"
                )

        # Proactively clean up driver after each resort check to ensure fresh session next time
        # This prevents "Connection refused" errors from stale drivers
        logger.info(
            f"Proactively cleaning up driver for {resort_name} to ensure fresh start next cycle"
        )
        cleanup_driver(resort_url, clear_profile=False)

    return was_blocked
