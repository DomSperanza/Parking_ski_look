"""
Resort URL Validation Script

Validates all resort URLs to ensure consistent scraping logic.
Checks CSS selectors, aria-label formats, and color values.
"""

import sys
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime
from dateutil import parser

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_db_connection


def get_resort_urls():
    """Get all resort URLs from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT resort_id, resort_name, resort_url, available_color, unavailable_color
            FROM resorts
            WHERE status = 'active'
            ORDER BY resort_name
        ''')
        
        resorts = cursor.fetchall()
        return [dict(resort) for resort in resorts]
    finally:
        conn.close()


def inspect_resort_url(resort_info):
    """
    Inspect a resort URL to verify scraping logic.
    
    Args:
        resort_info (dict): Resort information from database
        
    Returns:
        dict: Inspection results
    """
    print(f"\n{'='*60}")
    print(f"Inspecting: {resort_info['resort_name']}")
    print(f"URL: {resort_info['resort_url']}")
    print(f"{'='*60}")
    
    driver = None
    results = {
        'resort_name': resort_info['resort_name'],
        'url': resort_info['resort_url'],
        'success': False,
        'elements_found': [],
        'date_format': None,
        'color_values': {},
        'errors': []
    }
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(resort_info['resort_url'])
        
        # Wait for page to load
        wait = WebDriverWait(driver, 15)
        time.sleep(2)  # Extra time for dynamic content
        
        # Look for date elements with aria-label
        try:
            # Find all elements with aria-label attribute
            date_elements = driver.find_elements(By.CSS_SELECTOR, "[aria-label]")
            
            print(f"\nFound {len(date_elements)} elements with aria-label")
            
            # Filter for date-like aria-labels
            date_patterns = []
            for elem in date_elements[:20]:  # Check first 20
                aria_label = elem.get_attribute('aria-label')
                if aria_label:
                    # Check if it looks like a date
                    if any(word in aria_label.lower() for word in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                        date_patterns.append(aria_label)
                        bg_color = elem.value_of_css_property("background-color")
                        
                        results['elements_found'].append({
                            'aria_label': aria_label,
                            'background_color': bg_color,
                            'available': bg_color.strip() == resort_info['available_color']
                        })
                        
                        print(f"  - Date: {aria_label}")
                        print(f"    Color: {bg_color}")
                        print(f"    Available: {bg_color.strip() == resort_info['available_color']}")
            
            if date_patterns:
                # Analyze date format
                sample_date = date_patterns[0]
                results['date_format'] = sample_date
                print(f"\nDate format sample: {sample_date}")
                
                # Try to parse it
                try:
                    # Extract just the date part
                    date_part = sample_date.split(',')[1].strip() if ',' in sample_date else sample_date
                    parsed = parser.parse(date_part)
                    print(f"Parsed date: {parsed.strftime('%Y-%m-%d')}")
                except Exception as e:
                    print(f"Date parsing issue: {e}")
                    results['errors'].append(f"Date parsing: {e}")
            
            # Check color values found
            unique_colors = set()
            for elem_info in results['elements_found']:
                unique_colors.add(elem_info['background_color'])
            
            results['color_values'] = {
                'unique_colors_found': list(unique_colors),
                'expected_available': resort_info['available_color'],
                'expected_unavailable': resort_info['unavailable_color']
            }
            
            print(f"\nUnique colors found: {len(unique_colors)}")
            for color in unique_colors:
                print(f"  - {color}")
            
            results['success'] = True
            
        except Exception as e:
            print(f"Error finding date elements: {e}")
            results['errors'].append(str(e))
            
    except Exception as e:
        print(f"Error loading page: {e}")
        results['errors'].append(str(e))
        
    finally:
        if driver:
            driver.quit()
    
    return results


def main():
    """Main validation function."""
    print("Resort URL Validation Script")
    print("=" * 60)
    
    resorts = get_resort_urls()
    
    if not resorts:
        print("No active resorts found in database")
        return
    
    print(f"\nFound {len(resorts)} active resorts to validate")
    
    all_results = []
    for resort in resorts:
        results = inspect_resort_url(resort)
        all_results.append(results)
        time.sleep(2)  # Delay between resorts
    
    # Summary
    print(f"\n\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    
    for result in all_results:
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"\n{status} - {result['resort_name']}")
        print(f"  URL: {result['url']}")
        
        if result['date_format']:
            print(f"  Date Format: {result['date_format']}")
        
        if result['elements_found']:
            print(f"  Elements Found: {len(result['elements_found'])}")
        
        if result['errors']:
            print(f"  Errors:")
            for error in result['errors']:
                print(f"    - {error}")
    
    # Check for consistency
    print(f"\n\n{'='*60}")
    print("CONSISTENCY CHECK")
    print(f"{'='*60}")
    
    date_formats = [r['date_format'] for r in all_results if r['date_format']]
    if len(set(date_formats)) == 1:
        print("✓ All resorts use consistent date format")
    else:
        print("⚠ Date formats vary between resorts:")
        for i, fmt in enumerate(set(date_formats)):
            print(f"  Format {i+1}: {fmt}")
    
    colors = [r['color_values'] for r in all_results]
    available_colors = set([c['expected_available'] for c in colors])
    unavailable_colors = set([c['expected_unavailable'] for c in colors])
    
    if len(available_colors) == 1:
        print("✓ All resorts use consistent available color")
    else:
        print("⚠ Available colors vary:")
        for color in available_colors:
            print(f"  - {color}")
    
    if len(unavailable_colors) == 1:
        print("✓ All resorts use consistent unavailable color")
    else:
        print("⚠ Unavailable colors vary:")
        for color in unavailable_colors:
            print(f"  - {color}")


if __name__ == "__main__":
    main()

