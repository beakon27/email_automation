import sqlite3
import os
import sys

def migrate():
    """
    Add imap_verified_at field to the email_account table
    """
    # Get database path from environment variable or use default
    db_path = os.environ.get('EMAIL_DB_PATH', 'instance/email_automation.db')
    
    # Make sure path is relative to the application root
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', db_path)
    
    print(f"Using database at: {db_path}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the email_account table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_account'")
        if not cursor.fetchone():
            print("email_account table not found in database")
            return False
        
        # Check if the imap_verified_at column already exists
        cursor.execute("PRAGMA table_info(email_account)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'imap_verified_at' not in columns:
            print("Adding imap_verified_at column to email_account table")
            cursor.execute("ALTER TABLE email_account ADD COLUMN imap_verified_at TIMESTAMP")
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("imap_verified_at column already exists")
        
        return True
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return False
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1) 