"""
Database to CSV Exporter

Exports all tables from the SQLite database to individual CSV files.
Useful for debugging and data inspection.
"""

import os
import csv
import sqlite3
from pathlib import Path
from datetime import datetime

# Database path
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "parking_monitor.db"
EXPORT_DIR = Path(__file__).parent / "exports"

def export_db_to_csv():
    """
    Export all tables in the database to CSV files.
    """
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    # Create export directory if it doesn't exist
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_export_dir = EXPORT_DIR / timestamp
    current_export_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Exporting database to {current_export_dir}...")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table_name in tables:
            table_name = table_name[0]
            csv_path = current_export_dir / f"{table_name}.csv"
            
            print(f"Exporting table: {table_name}")
            
            # Get all data from table
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Get column names
            column_names = [description[0] for description in cursor.description]
            
            # Write to CSV
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(column_names)  # Header
                writer.writerows(rows)         # Data
                
        print(f"\nSuccess! Exported {len(tables)} tables.")
        print(f"Files located in: {current_export_dir}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_db_to_csv()
