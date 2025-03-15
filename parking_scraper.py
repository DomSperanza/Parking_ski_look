from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime
import os

# Configuration
URL = "https://reservenski.parkbrightonresort.com/select-parking"
CHECK_INTERVAL = 5  # Seconds between checks
TARGET_ARIA_LABEL = "Sunday, March 16, 2025"
# When the date is not available, its color is:
UNAVAILABLE_COLOR = "rgb(247, 205, 212)"

def main():
    """Main function to check date availability by inspecting its color."""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get(URL)
    
    try:
        check_count = 0
        while True:
            check_count += 1
            print(f"\n--- Check #{check_count} ---")
            
            # Wait for the page to load and the target date element to be present.
            wait = WebDriverWait(driver, 30)
            try:
                date_element = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, f"[aria-label='{TARGET_ARIA_LABEL}']")
                    )
                )
            except Exception as e:
                print(f"Could not locate element with aria-label '{TARGET_ARIA_LABEL}': {e}")
                driver.refresh()
                continue
            
            # Wait 1 second for the final dynamic content to load fully.
            time.sleep(5)
            
            # Get computed color of the element.
            color = date_element.value_of_css_property("color")
            print(f"Color for '{TARGET_ARIA_LABEL}' is {color}")
            
            if color.strip() == UNAVAILABLE_COLOR:
                print("Date is NOT available.")
            else:
                print("\n🚨 ALERT! Date IS available! 🚨")
                for _ in range(5):
                    print('\a')  # Bell sound (may work in some terminals)
                    time.sleep(0.5)
                input("Press Enter to continue monitoring...")
            
            print(f"Waiting {CHECK_INTERVAL} seconds before refreshing...")
            time.sleep(CHECK_INTERVAL)
            driver.refresh()
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main() 