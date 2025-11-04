#!/usr/bin/env python3
"""
Query User Selections Script

Shows how to query user resort and date selections from the database.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config.database import get_user_selections, get_all_users_with_selections

def show_user_selections(user_id):
    """Show selections for a specific user."""
    print(f"🔍 User {user_id} Selections:")
    print("-" * 40)
    
    selections = get_user_selections(user_id)
    
    if not selections:
        print("No selections found for this user.")
        return
    
    for selection in selections:
        print(f"Resort: {selection['resort_name']}")
        print(f"Date: {selection['target_date']}")
        print(f"Status: {selection['status']}")
        print(f"Created: {selection['created_at']}")
        print()

def show_all_users():
    """Show all users with their selections."""
    print("👥 All Users and Their Selections:")
    print("=" * 50)
    
    users = get_all_users_with_selections()
    
    for user in users:
        print(f"User ID: {user['user_id']}")
        print(f"Email: {user['email']}")
        print(f"PIN: {user['pin']}")
        print(f"Created: {user['created_at']}")
        
        if user['selections']:
            print("Selections:")
            for selection in user['selections']:
                print(f"  - {selection['resort_name']} on {selection['target_date']} ({selection['job_status']})")
        else:
            print("No selections")
        
        print("-" * 30)

def main():
    """Main function."""
    print("📊 User Selections Query Tool")
    print("=" * 40)
    
    # Show all users
    show_all_users()
    
    # Show specific user if provided
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
            show_user_selections(user_id)
        except ValueError:
            print("❌ Please provide a valid user ID (integer)")
    else:
        print("\n💡 To see specific user selections, run:")
        print("python query_user_selections.py <user_id>")

if __name__ == "__main__":
    main()
