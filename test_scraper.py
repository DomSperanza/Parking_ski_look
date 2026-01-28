#!/usr/bin/env python3
"""
Quick test script for parking scraper
Usage: python test_scraper.py [resort_url] [date]
Example: python test_scraper.py "https://reserve.parkatparkcitymountain.com/select-parking" "2026-01-30"
"""

import sys
import logging
from pathlib import Path

# Setup path
sys.path.append(str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from monitoring.parking_scraper_v3 import check_multiple_dates, cleanup_all_drivers

# Test configurations
RESORTS = {
    "park_city": "https://reserve.parkatparkcitymountain.com/select-parking",
    "brighton": "https://reservenski.parkbrightonresort.com/select-parking",
    "alta": "https://reservenski.skialta.com/select-parking",
    "solitude": "https://reservenski.solitudemountain.com/select-parking",
}


def main():
    if len(sys.argv) >= 3:
        resort_url = sys.argv[1]
        dates = sys.argv[2:]
    else:
        print("\nAvailable resorts:")
        for name, url in RESORTS.items():
            print(f"  {name}: {url}")
        
        print("\nUsage examples:")
        print(f"  python test_scraper.py \"{RESORTS['park_city']}\" \"2026-01-30\"")
        print(f"  python test_scraper.py \"{RESORTS['brighton']}\" \"2026-01-31\" \"2026-02-01\"")
        print("\nOr use shorthand:")
        print("  python test_scraper.py park_city \"2026-01-30\"")
        sys.exit(1)
    
    # Check if first arg is a shorthand resort name
    if resort_url in RESORTS:
        resort_url = RESORTS[resort_url]
    
    print(f"\n{'='*60}")
    print(f"Testing: {resort_url}")
    print(f"Dates: {', '.join(dates)}")
    print(f"{'='*60}\n")
    
    try:
        results = check_multiple_dates(resort_url, dates)
        
        print(f"\n{'='*60}")
        print("RESULTS:")
        print(f"{'='*60}")
        for date, status in results.items():
            icon = "✓" if status == "green" else "✗" if status == "red" else "?" if status == "blank" else "⚠"
            print(f"  {icon} {date}: {status.upper()}")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up drivers...")
        cleanup_all_drivers()
        print("Done!")


if __name__ == "__main__":
    main()

