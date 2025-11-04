"""
Parking Scraper V3

Simple scraper to check parking availability by detecting background color on date elements.
Returns: "green" (available), "red" (unavailable), or "blank" (not found).
"""

import sys
from pathlib import Path
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

sys.path.append(str(Path(__file__).parent.parent))

from utils.date_converter import convert_to_aria_label

# Green color for available dates (from HTML examples)
AVAILABLE_GREEN = "rgba(49, 200, 25, 0.2)"


def check_date_availability(resort_url, date_str):
    """
    Check if a specific date has parking available.
    
    Args:
        resort_url (str): URL of the resort parking page
        date_str (str): Date in YYYY-MM-DD format or aria-label format
    
    Returns:
        str: "green" if available, "red" if unavailable, "blank" if not found
    """
    driver = None
    
    try:
        # Convert date to aria-label format if needed
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            aria_label = convert_to_aria_label(date_str)
        else:
            aria_label = date_str
        
        # Setup Chrome with headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        driver.get(resort_url)
        
        # Wait for calendar to load
        wait = WebDriverWait(driver, 30)
        time.sleep(8)
        
        # Try to find the date element by aria-label
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
        
        # Check for inline style attribute with green background
        style_attr = date_element.get_attribute("style")
        
        if style_attr and "background-color" in style_attr.lower():
            # Check if it contains the green color
            if AVAILABLE_GREEN in style_attr:
                return "green"
            else:
                # Has background-color but not green = unavailable
                return "red"
        else:
            # No inline background-color style = unavailable
            return "red"
        
    except WebDriverException as e:
        print(f"WebDriver error: {e}")
        return "blank"
    except Exception as e:
        print(f"Error checking date: {e}")
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
    
    Args:
        resort_url (str): URL of the resort parking page
        date_list (list): List of dates in YYYY-MM-DD format
    
    Returns:
        dict: Mapping of date -> status ("green", "red", or "blank")
    """
    driver = None
    results = {}
    
    try:
        # Setup Chrome with headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        driver.get(resort_url)
        
        # Wait for calendar to load
        wait = WebDriverWait(driver, 30)
        time.sleep(8)
        
        # Check each date in the same session
        for date_str in date_list:
            # Convert date to aria-label format if needed
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                aria_label = convert_to_aria_label(date_str)
            else:
                aria_label = date_str
            
            try:
                # Try to find the date element (page already loaded, use short timeout)
                try:
                    date_element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, f"[aria-label='{aria_label}']")
                        )
                    )
                except TimeoutException:
                    results[date_str] = "blank"
                    continue
                
                # Check for inline style attribute with green background
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
        print(f"WebDriver error: {e}")
        # Return blank for all dates on error
        return {date_str: "blank" for date_str in date_list}
    except Exception as e:
        print(f"Error: {e}")
        return {date_str: "blank" for date_str in date_list}
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
