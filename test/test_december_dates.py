"""
Test script to check all December 2025 dates for parking availability across all 4 ski resorts.
"""

import sys
from pathlib import Path
import csv

sys.path.append(str(Path(__file__).parent.parent))

from monitoring.parking_scraper_v3 import check_multiple_dates
from datetime import datetime, timedelta

# Resorts list - using resorts.csv
RESORTS_CSV = Path(__file__).parent.parent / "data" / "csvs" / "resorts.csv"

def get_resorts():
    """Load resorts from CSV file."""
    resorts = []
    with open(RESORTS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['status'] == 'active':
                resorts.append({
                    'name': row['resort_name'],
                    'url': row['resort_url']
                })
    return resorts

def get_december_dates():
    """Generate all dates in December 2025."""
    dates = []
    start_date = datetime(2025, 12, 1)
    
    for day in range(31):
        date = start_date + timedelta(days=day)
        dates.append(date.strftime('%Y-%m-%d'))
    
    return dates

def check_resort(resort_name, resort_url, dates):
    """Check a single resort and return results."""
    print(f"\n{'=' * 70}")
    print(f"Checking {resort_name}")
    print(f"URL: {resort_url}")
    print("Loading page and checking all dates in single session...\n")
    
    # Check all dates in one browser session
    results = check_multiple_dates(resort_url, dates)
    
    available = []
    unavailable = []
    not_found = []
    
    for date_str, status in results.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        if status == "green":
            available.append(date_str)
            print(f"{date_obj.strftime('%Y-%m-%d (%A)')}: AVAILABLE (green)")
        elif status == "red":
            unavailable.append(date_str)
            print(f"{date_obj.strftime('%Y-%m-%d (%A)')}: UNAVAILABLE (red)")
        else:
            not_found.append(date_str)
            print(f"{date_obj.strftime('%Y-%m-%d (%A)')}: NOT FOUND (blank)")
    
    print(f"\n{resort_name} Summary:")
    print(f"  Available (green): {len(available)} dates")
    print(f"  Unavailable (red): {len(unavailable)} dates")
    print(f"  Not found (blank): {len(not_found)} dates")
    
    if available:
        print(f"\n  Available dates:")
        for date_str in available:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            print(f"    - {date_obj.strftime('%Y-%m-%d (%A)')}")
    
    return {
        'available': available,
        'unavailable': unavailable,
        'not_found': not_found
    }

def main():
    print("=" * 70)
    print("DECEMBER 2025 PARKING AVAILABILITY CHECK")
    print("Checking all 4 ski resorts")
    print("=" * 70)
    
    resorts = get_resorts()
    dates = get_december_dates()
    
    all_results = {}
    
    for resort in resorts:
        results = check_resort(resort['name'], resort['url'], dates)
        all_results[resort['name']] = results
    
    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY - All Resorts")
    print("=" * 70)
    
    for resort_name, results in all_results.items():
        print(f"\n{resort_name}:")
        print(f"  Available: {len(results['available'])} dates")
        print(f"  Unavailable: {len(results['unavailable'])} dates")
        print(f"  Not found: {len(results['not_found'])} dates")

if __name__ == "__main__":
    main()

