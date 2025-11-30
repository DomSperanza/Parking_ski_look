#!/usr/bin/env python3
"""
Database to CSV Export Script

Exports all tables from parking_monitor.db to CSV files in data/csvs/
"""

import sqlite3
import csv
import os
import sys
from pathlib import Path
from datetime import datetime

def get_db_connection():
    """Get database connection."""
    db_path = Path(__file__).parent / "data" / "parking_monitor.db"
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        return None
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def get_table_names(conn):
    """Get all table names from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def export_table_to_csv(conn, table_name, output_dir):
    """Export a single table to CSV."""
    cursor = conn.cursor()
    
    # Get all data from table
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    if not rows:
        print(f"⚠️  Table '{table_name}' is empty")
        return False
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    
    # Create CSV file
    csv_path = output_dir / f"{table_name}.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(column_names)
        
        # Write data rows
        for row in rows:
            writer.writerow(row)
    
    print(f"✅ Exported {len(rows)} rows from '{table_name}' to {csv_path.name}")
    return True

def main():
    """Main function to export all tables to CSV."""
    print("📊 Database to CSV Export Tool")
    print("=" * 40)
    
    # Create output directory
    output_dir = Path(__file__).parent / "data" / "csvs"
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        return 1
    
    try:
        # Get all table names
        tables = get_table_names(conn)
        print(f"📋 Found {len(tables)} tables: {', '.join(tables)}")
        
        if not tables:
            print("❌ No tables found in database")
            return 1
        
        # Export each table
        exported_count = 0
        for table_name in tables:
            if export_table_to_csv(conn, table_name, output_dir):
                exported_count += 1
        
        print("\n" + "=" * 40)
        print(f"🎉 Successfully exported {exported_count}/{len(tables)} tables")
        print(f"📁 CSV files saved to: {output_dir}")
        
        # Show file sizes
        print("\n📊 File sizes:")
        for csv_file in output_dir.glob("*.csv"):
            size = csv_file.stat().st_size
            print(f"   {csv_file.name}: {size:,} bytes")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error during export: {e}")
        return 1
    
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())




