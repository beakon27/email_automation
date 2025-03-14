#!/usr/bin/env python3
"""
Reset Application Script

This script resets the SQLAlchemy metadata and checks the database schema
to ensure the ORM recognizes all columns correctly.
"""

import os
import sys
import sqlite3
import logging
from sqlalchemy import MetaData, Table, inspect

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def verify_database_structure(db_path):
    """Verify the database structure and display column information"""
    logger.info(f"Verifying database structure at: {db_path}")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Connect directly to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    logger.info(f"Tables in database: {[t[0] for t in tables]}")
    
    # Check email_account table specifically
    if not any(t[0] == 'email_account' for t in tables):
        logger.error("email_account table not found!")
        conn.close()
        return False
    
    # Get columns for email_account
    cursor.execute("PRAGMA table_info(email_account)")
    columns = cursor.fetchall()
    column_info = [f"{col[1]} ({col[2]})" for col in columns]
    logger.info(f"email_account columns: {column_info}")
    
    # Check if imap_verified_at exists
    if any(col[1] == 'imap_verified_at' for col in columns):
        logger.info("imap_verified_at column exists in database schema!")
    else:
        logger.error("imap_verified_at column NOT FOUND in database schema!")
        
        # Try to add it
        try:
            logger.info("Attempting to add imap_verified_at column...")
            cursor.execute("ALTER TABLE email_account ADD COLUMN imap_verified_at TIMESTAMP")
            conn.commit()
            logger.info("Successfully added imap_verified_at column!")
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to add column: {str(e)}")
    
    conn.close()
    return True

def reset_app():
    """Reset the Flask application by modifying the database configuration."""
    # Import the app after creating a clean environment
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Try importing the app without initializing SQLAlchemy
        from app import app as flask_app
        
        # Get database path
        db_uri = flask_app.config['SQLALCHEMY_DATABASE_URI']
        db_path = db_uri.replace('sqlite:///', '')
        
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
            
        logger.info(f"Database URI: {db_uri}")
        logger.info(f"Database path: {db_path}")
        
        # Verify database structure
        verify_database_structure(db_path)
        
        # Write a flag file to indicate we need to reset SQLAlchemy on next startup
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.reset_sqlalchemy'), 'w') as f:
            f.write('1')
        
        logger.info("Created reset flag file for next application startup")
        logger.info("Application has been reset. Restart the application to apply changes.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error resetting application: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if reset_app():
        logger.info("Application reset completed successfully")
        sys.exit(0)
    else:
        logger.error("Application reset failed")
        sys.exit(1) 