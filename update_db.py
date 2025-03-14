"""
Update database script for email automation system.

This script updates the database schema to add the campaign_id column to the email table
and creates the Campaign table if it doesn't exist.
"""

import sqlite3
import logging
import os
from app import db, app
from app.models.models import Campaign, Email

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_database():
    """Update the database schema to include campaign_id column and Campaign table."""
    try:
        # Get the database path
        db_path = os.path.join(os.path.dirname(__file__), 'email_automation.db')
        logger.info(f"Connecting to database at {db_path}")
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if Campaign table exists and create if not
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
            cursor.execute("ALTER TABLE email ADD COLUMN campaign_id INTEGER REFERENCES campaign(id)")
        else:
            logger.info("campaign_id column already exists in email table")
        
        # Commit changes
        conn.commit()
        logger.info("Database schema update completed successfully")
        
    except Exception as e:
        logger.error(f"Error updating database schema: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
    
    logger.info("Database update operation completed")

if __name__ == "__main__":
    with app.app_context():
        update_database()
        logger.info("Database schema has been updated.") 