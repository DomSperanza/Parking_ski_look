import requests

# URL of the webpage you want to inspect
URL = "https://reservenski.parkbrightonresort.com/select-parking"  # Replace with your target URL

def fetch_html():
    try:
        response = requests.get(URL)
        response.raise_for_status()  # Raise an error for bad HTTP responses
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None

def save_html(html_content, filename="page.html"):
    if html_content:
        with open(filename, "w", encoding="utf-8") as file:
            file.write(html_content)
        print(f"HTML content saved to {filename}")

if __name__ == "__main__":
    html = fetch_html()
    if html:
        save_html(html) 