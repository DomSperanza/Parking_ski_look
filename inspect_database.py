#!/usr/bin/env python3
"""
Database Inspection Script

Shows how to get column names and table information from SQLite database.
"""

import sys
from pathlib import Path

# Add config to path
sys.path.append(str(Path(__file__).parent))

from config.database import get_db_connection

def get_table_columns(table_name):
    """
    Get column information for a specific table.
    
    Args:
        table_name (str): Name of the table
    
    Returns:
        list: List of column information dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return [dict(column) for column in columns]
    except Exception as e:
        print(f"Error getting columns for {table_name}: {e}")
        return []
    finally:
        conn.close()

def get_all_tables():
    """
    Get all table names in the database.
    
    Returns:
        list: List of table names
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        return [table[0] for table in tables]
    except Exception as e:
        print(f"Error getting tables: {e}")
        return []
    finally:
        conn.close()

def get_table_schema(table_name):
    """
    Get the complete schema for a table.
    
    Args:
        table_name (str): Name of the table
    
    Returns:
        str: SQL CREATE statement for the table
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting schema for {table_name}: {e}")
        return None
    finally:
        conn.close()

def inspect_database():
    """Inspect the database structure."""
    print("🔍 Database Inspection")
    print("=" * 50)
    
    # Get all tables
    tables = get_all_tables()
    print(f"📊 Found {len(tables)} tables: {', '.join(tables)}")
    print()
    
    # Inspect each table
    for table_name in tables:
        print(f"📋 Table: {table_name}")
        print("-" * 30)
        
        # Get column information
        columns = get_table_columns(table_name)
        
        if columns:
            print("Columns:")
            for col in columns:
                # Format column info nicely
                nullable = "NULL" if col['notnull'] == 0 else "NOT NULL"
                default = f" DEFAULT {col['dflt_value']}" if col['dflt_value'] is not None else ""
                pk = " PRIMARY KEY" if col['pk'] == 1 else ""
                
                print(f"  • {col['name']} ({col['type']}) {nullable}{default}{pk}")
        else:
            print("  No columns found")
        
        print()

def get_column_names(table_name):
    """
    Get just the column names for a table.
    
    Args:
        table_name (str): Name of the table
    
    Returns:
        list: List of column names
    """
    columns = get_table_columns(table_name)
    return [col['name'] for col in columns]

def get_sample_data(table_name, limit=5):
    """
    Get sample data from a table.
    
    Args:
        table_name (str): Name of the table
        limit (int): Number of rows to return
    
    Returns:
        list: List of sample rows
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting sample data from {table_name}: {e}")
        return []
    finally:
        conn.close()

def main():
    """Main inspection function."""
    # Full database inspection
    inspect_database()
    
    print("\n" + "=" * 50)
    print("🔧 Quick Reference - Column Names")
    print("=" * 50)
    
    # Show column names for each table
    tables = get_all_tables()
    for table_name in tables:
        column_names = get_column_names(table_name)
        print(f"{table_name}: {', '.join(column_names)}")
    
    print("\n" + "=" * 50)
    print("📝 Sample Data")
    print("=" * 50)
    
    # Show sample data
    for table_name in tables:
        sample_data = get_sample_data(table_name, 3)
        if sample_data:
            print(f"\n{table_name} (sample):")
            for row in sample_data:
                print(f"  {dict(row)}")

if __name__ == "__main__":
    main()
