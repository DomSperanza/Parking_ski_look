import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from monitoring.parking_scraper_v3 import check_multiple_dates, cleanup_all_drivers

RESORTS = {
    "park_city": "https://reserve.parkatparkcitymountain.com/select-parking",
    "brighton": "https://reservenski.parkbrightonresort.com/select-parking",
    "solitude": "https://reserve.parkatsolitude.com/select-parking",
    "alta": "https://reserve.altaparking.com/select-parking",
}

DATES = ["2026-02-14", "2026-02-15", "2026-02-16"]


def main():
    print("Starting Comprehensive Test for Feb 14-16, 2026")
    print("=" * 60)

    overall_results = {}

    for name, url in RESORTS.items():
        print(f"\nTesting: {name.upper()}")
        print("-" * 60)
        try:
            results = check_multiple_dates(url, DATES)
            overall_results[name] = results
            for date, status in results.items():
                print(f"  {date}: {status}")
        except Exception as e:
            print(f"  ERROR: {e}")
            overall_results[name] = "ERROR"

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    for name, res in overall_results.items():
        print(f"{name.upper()}:")
        if isinstance(res, dict):
            for date, status in res.items():
                icon = "✓" if status == "green" else "✗" if status == "red" else "⚠"
                print(f"  {icon} {date}: {status}")
        else:
            print(f"  ⚠ {res}")

    cleanup_all_drivers()


if __name__ == "__main__":
    main()
