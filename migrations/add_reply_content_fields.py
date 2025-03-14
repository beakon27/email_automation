"""
Database migration script to add reply content fields to the email table.
"""

import os
import sys
import sqlite3
import logging

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Add response_subject and response_content columns to the email table
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import app configuration
        from app import app
        
        logger.info("Running migration to add reply content fields to email table")
        
        # Get database URI from app config
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Only works for SQLite
        if not db_uri.startswith('sqlite:///'):
            logger.error("Migration only supports SQLite databases")
            return False
            
        # Extract database path
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
        
        logger.info(f"Using database at {db_path}")
        
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if the columns already exist
            cursor.execute("PRAGMA table_info(email)")
            columns = [col[1] for col in cursor.fetchall()]
            
            changes_made = False
            
            # Add the response_subject column if it doesn't exist
            if 'response_subject' not in columns:
                logger.info("Adding response_subject column")
                cursor.execute("ALTER TABLE email ADD COLUMN response_subject TEXT")
                changes_made = True
                
            # Add the response_content column if it doesn't exist
            if 'response_content' not in columns:
                logger.info("Adding response_content column")
                cursor.execute("ALTER TABLE email ADD COLUMN response_content TEXT")
                changes_made = True
                
            if changes_made:
                conn.commit()
                logger.info("Successfully added reply content fields to email table")
            else:
                logger.info("Reply content fields already exist, no changes needed")
                
            return True
            
        except Exception as e:
            logger.error(f"Error during migration: {str(e)}")
            return False
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Migration error: {str(e)}")
        return False

if __name__ == "__main__":
    if migrate():
        print("Migration completed successfully")
    else:
        print("Migration failed") 