"""
Date Conversion Utility

Converts dates from database format (YYYY-MM-DD) to aria-label format
used by the parking reservation websites (e.g., "Sunday, March 16, 2025").
"""

from datetime import datetime
import pytz


def convert_to_aria_label(date_str, timezone='America/Denver'):
    """
    Convert date from YYYY-MM-DD format to aria-label format.
    
    Args:
        date_str (str): Date in YYYY-MM-DD format
        timezone (str): Timezone string (default: 'America/Denver')
    
    Returns:
        str: Date in aria-label format (e.g., "Sunday, March 16, 2025")
    
    Raises:
        ValueError: If date_str is not in valid YYYY-MM-DD format
    """
    try:
        # Parse the date string
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get timezone
        tz = pytz.timezone(timezone)
        
        # Create datetime at midnight in the specified timezone
        dt = tz.localize(datetime.combine(date_obj, datetime.min.time()))
        
        # Format as aria-label: "DayName, Month Day, Year"
        day_name = dt.strftime('%A')
        month_name = dt.strftime('%B')
        day = dt.day
        year = dt.year
        
        aria_label = f"{day_name}, {month_name} {day}, {year}"
        
        return aria_label
        
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD") from e


def convert_from_aria_label(aria_label):
    """
    Convert date from aria-label format to YYYY-MM-DD format.
    
    Args:
        aria_label (str): Date in aria-label format (e.g., "Sunday, March 16, 2025")
    
    Returns:
        str: Date in YYYY-MM-DD format
    """
    try:
        # Parse aria-label format: "DayName, Month Day, Year"
        # Remove day name and comma
        date_part = aria_label.split(',', 1)[1].strip()
        
        # Parse the remaining part: "Month Day, Year"
        date_obj = datetime.strptime(date_part, '%B %d, %Y')
        
        return date_obj.strftime('%Y-%m-%d')
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid aria-label format '{aria_label}'") from e


if __name__ == "__main__":
    # Test conversions
    test_date = "2025-03-16"
    aria = convert_to_aria_label(test_date)
    print(f"{test_date} -> {aria}")
    
    back = convert_from_aria_label(aria)
    print(f"{aria} -> {back}")
    
    assert back == test_date, "Round-trip conversion failed"

