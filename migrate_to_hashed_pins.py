#!/usr/bin/env python3
"""
Migration Script: Convert existing PINs to SHA-256 hashes

This script migrates existing users from raw PIN storage to secure SHA-256 hashing.
"""

import sys
import hashlib
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config.database import get_db_connection

def create_user_hash(email, pin):
    """Create a SHA-256 hash from email and PIN."""
    combined = f"{email.lower().strip()}:{pin}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def migrate_pins():
    """Migrate existing PINs to hashed format."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all users with non-hashed PINs (assuming they're 6 digits or UUIDs)
        cursor.execute('SELECT user_id, email, pin FROM users')
        users = cursor.fetchall()
        
        migrated_count = 0
        skipped_count = 0
        
        print(f"Found {len(users)} users to check...")
        
        for user_id, email, pin in users:
            # Check if PIN is already hashed (64 characters = SHA-256)
            if len(pin) == 64 and all(c in '0123456789abcdef' for c in pin.lower()):
                print(f"User {user_id} ({email}): Already hashed - skipping")
                skipped_count += 1
                continue
            
            # Check if PIN looks like a UUID (36 characters with dashes)
            if len(pin) == 36 and '-' in pin:
                print(f"User {user_id} ({email}): UUID found - needs manual migration")
                print(f"  Current PIN: {pin}")
                print(f"  This user needs to provide their 6-digit PIN for migration")
                skipped_count += 1
                continue
            
            # Check if PIN is 6 digits (valid format)
            if pin.isdigit() and len(pin) == 6:
                # Create hash from email + PIN
                new_hash = create_user_hash(email, pin)
                
                # Update user with hashed PIN
                cursor.execute('UPDATE users SET pin = ? WHERE user_id = ?', (new_hash, user_id))
                
                print(f"User {user_id} ({email}): Migrated PIN {pin} -> {new_hash[:16]}...")
                migrated_count += 1
            else:
                print(f"User {user_id} ({email}): Invalid PIN format '{pin}' - skipping")
                skipped_count += 1
        
        conn.commit()
        
        print(f"\nMigration complete!")
        print(f"Migrated: {migrated_count} users")
        print(f"Skipped: {skipped_count} users")
        
        if skipped_count > 0:
            print(f"\nNote: Some users were skipped and may need manual attention.")
            print(f"Users with UUIDs as PINs need to provide their 6-digit PIN.")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main migration function."""
    print("🔐 PIN Migration Tool")
    print("=" * 40)
    print("This will convert existing PINs to secure SHA-256 hashes.")
    print("WARNING: This will modify your database!")
    print()
    
    response = input("Do you want to continue? (yes/no): ").lower().strip()
    if response != 'yes':
        print("Migration cancelled.")
        return 1
    
    if migrate_pins():
        print("\n✅ Migration completed successfully!")
        return 0
    else:
        print("\n❌ Migration failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
