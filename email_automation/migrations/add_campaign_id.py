"""
Migration script to add campaign_id to Email table and create Campaign table.
"""

import sqlite3
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration(db_path):
    """
    Run the migration to add campaign_id to Email table and create Campaign table
    
    Args:
        db_path (str): Path to the SQLite database file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting migration on database: {db_path}")
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Check if Campaign table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaign'")
        if not cursor.fetchone():
            logger.info("Creating Campaign table")
            cursor.execute("""
            CREATE TABLE campaign (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                template_id INTEGER,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES email_template (id)
            )
            """)
        else:
            logger.info("Campaign table already exists")
        
        # Check if email table has campaign_id column
        cursor.execute("PRAGMA table_info(email)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'campaign_id' not in columns:
            logger.info("Adding campaign_id column to email table")
            cursor.execute("ALTER TABLE email ADD COLUMN campaign_id INTEGER")
            cursor.execute("CREATE INDEX idx_email_campaign_id ON email (campaign_id)")
        else:
            logger.info("campaign_id column already exists in email table")
        
        # Check if EmailStatus enum has PAUSED value
        cursor.execute("SELECT type FROM sqlite_master WHERE type='table' AND name='email'")
        if cursor.fetchone():
            # Get the current enum values
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='email'")
            table_sql = cursor.fetchone()[0]
            
            # Check if PAUSED is already in the enum
            if "PAUSED" not in table_sql:
                logger.info("Adding PAUSED to EmailStatus enum")
                logger.warning("SQLite doesn't support altering enum types directly.")
                logger.warning("You'll need to update the enum in the code and restart the application.")
        
        # Commit the transaction
        conn.commit()
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return False
        
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default path relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(os.path.dirname(script_dir), 'email_automation.db')
    
    success = run_migration(db_path)
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1) 