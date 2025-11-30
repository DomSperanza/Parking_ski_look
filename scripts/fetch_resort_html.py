from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

RESORTS = [
    {"name": "Brighton", "url": "https://reservenski.parkbrightonresort.com/select-parking"},
    {"name": "Solitude", "url": "https://reservenski.parksolitude.com/select-parking"},
    {"name": "Alta", "url": "https://reserve.altaparking.com/select-parking"},
    {"name": "Park_City", "url": "https://reserve.parkatparkcitymountain.com/select-parking"},
]

def fetch_dynamic_html(url):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    
    try:
        driver.get(url)
        time.sleep(5)
        html_content = driver.page_source
    finally:
        driver.quit()
    
    return html_content

if __name__ == "__main__":
    output_dir = "html_examples"
    os.makedirs(output_dir, exist_ok=True)
    
    for resort in RESORTS:
        print(f"Fetching HTML for {resort['name']}...")
        html = fetch_dynamic_html(resort['url'])
        if html:
            filename = os.path.join(output_dir, f"{resort['name'].lower()}.html")
            with open(filename, "w", encoding="utf-8") as file:
                file.write(html)
            print(f"Saved to {filename}")
        else:
            print(f"Failed to fetch HTML for {resort['name']}")
    
    print("Done fetching all resort HTML files.")

