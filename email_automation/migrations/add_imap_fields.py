"""
Database migration script to add IMAP fields to the email_account table.
This script should be run manually after deploying the code changes.

Usage:
    python migrations/add_imap_fields.py
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

def migrate():
    """
    Migrate the database to add IMAP fields
    
    Returns:
        bool: True if migration was successful, False if error or not needed
    """
    try:
        # Don't import these at the module level to avoid circular imports
        from app import app
        
        print("Running database migration to add IMAP fields to email_account table...")
        
        # Get database URI from app config
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Extract database path from URI for SQLite
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            # Adjust for relative paths
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
            
            print(f"Using SQLite database at: {db_path}")
            
            try:
                # Connect to SQLite database
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check if the columns already exist
                cursor.execute("PRAGMA table_info(email_account)")
                columns = [col[1] for col in cursor.fetchall()]
                
                columns_to_add = []
                if 'imap_server' not in columns:
                    columns_to_add.append(('imap_server', 'TEXT'))
                if 'imap_port' not in columns:
                    columns_to_add.append(('imap_port', 'INTEGER DEFAULT 993'))
                if 'imap_username' not in columns:
                    columns_to_add.append(('imap_username', 'TEXT'))
                if 'imap_password' not in columns:
                    columns_to_add.append(('imap_password', 'TEXT'))
                if 'imap_enabled' not in columns:
                    columns_to_add.append(('imap_enabled', 'BOOLEAN DEFAULT 0'))
                    
                if not columns_to_add:
                    print("IMAP columns already exist in the database. No migration needed.")
                    return True
                    
                # Add new columns
                for column_name, column_type in columns_to_add:
                    print(f"Adding column {column_name} ({column_type}) to email_account table...")
                    cursor.execute(f"ALTER TABLE email_account ADD COLUMN {column_name} {column_type}")
                    
                # Pre-populate IMAP fields based on SMTP settings
                print("Pre-populating IMAP fields based on SMTP settings...")
                cursor.execute("""
                    UPDATE email_account
                    SET 
                        imap_server = REPLACE(smtp_server, 'smtp', 'imap'),
                        imap_username = smtp_username,
                        imap_password = smtp_password,
                        imap_port = 993
                    WHERE imap_server IS NULL
                """)
                
                # Commit changes
                conn.commit()
                print("Database migration completed successfully!")
                return True
                
            except sqlite3.Error as e:
                print(f"SQLite error: {e}")
                return False
            finally:
                if conn:
                    conn.close()
        else:
            print(f"Unsupported database type: {db_uri}")
            print("Please manually add the following columns to the email_account table:")
            print("- imap_server (TEXT)")
            print("- imap_port (INTEGER DEFAULT 993)")
            print("- imap_username (TEXT)")
            print("- imap_password (TEXT)")
            print("- imap_enabled (BOOLEAN DEFAULT 0)")
            return False
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed or was not needed.") 