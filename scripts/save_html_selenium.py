from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def fetch_dynamic_html(url):
    # Set up the Chrome WebDriver using the webdriver_manager package
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    
    try:
        driver.get(url)
        # Wait for dynamic content to load. Adjust based on your webpage.
        time.sleep(5)
        html_content = driver.page_source
    finally:
        driver.quit()
    
    return html_content

if __name__ == "__main__":
    URL = "https://reservenski.parkbrightonresort.com/select-parking"  # Replace with your target URL
    html = fetch_dynamic_html(URL)
    if html:
        with open("dynamic_page2.html", "w", encoding="utf-8") as file:
            file.write(html)
        print("Rendered HTML saved to dynamic_page.html") 