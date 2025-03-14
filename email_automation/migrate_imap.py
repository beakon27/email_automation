#!/usr/bin/env python3
"""
IMAP Migration Script

This script directly adds the imap_verified_at column to the email_account table.
Run this script directly with Python to fix the database schema.
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def migrate_imap_verified_column(db_path):
    """Add imap_verified_at column to the email_account table"""
    logger.info(f"Starting IMAP migration for database: {db_path}")
    
    # Check if file exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Print the schema of email_account table
        cursor.execute("PRAGMA table_info(email_account)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"Current email_account columns: {column_names}")
        
        # Check if column already exists
        if 'imap_verified_at' in column_names:
            logger.info("imap_verified_at column already exists!")
            conn.close()
            return True
            
        logger.info("imap_verified_at column DOES NOT EXIST - proceeding with migration")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Tables in database: {[t[0] for t in tables]}")
        
        # Try to add the column using ALTER TABLE first
        try:
            logger.info("Adding imap_verified_at column using ALTER TABLE")
            cursor.execute("ALTER TABLE email_account ADD COLUMN imap_verified_at TIMESTAMP")
            conn.commit()
            logger.info("Column added successfully using ALTER TABLE")
        except sqlite3.OperationalError as e:
            logger.error(f"ALTER TABLE failed: {str(e)}")
            
            # More aggressive approach - force table recreation
            logger.info("Trying table recreation approach")
            
            try:
                # Backup the current table data
                cursor.execute("BEGIN TRANSACTION")
                
                # Get the current schema
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='email_account'")
                create_stmt = cursor.fetchone()[0]
                logger.info(f"Original create statement: {create_stmt}")
                
                # Create temp table for backup
                cursor.execute("CREATE TABLE email_account_temp AS SELECT * FROM email_account")
                
                # Drop the original table
                cursor.execute("DROP TABLE email_account")
                
                # Create a new table with the imap_verified_at column
                modified_create = create_stmt
                if 'imap_verified_at' not in modified_create:
                    # Find the closing parenthesis and insert our column before it
                    last_paren_index = modified_create.rindex(")")
                    modified_create = modified_create[:last_paren_index] + ", imap_verified_at TIMESTAMP" + modified_create[last_paren_index:]
                
                logger.info(f"Modified create statement: {modified_create}")
                cursor.execute(modified_create)
                
                # Get column names from temp table
                cursor.execute("PRAGMA table_info(email_account_temp)")
                temp_columns = [col[1] for col in cursor.fetchall()]
                columns_str = ", ".join(temp_columns)
                
                # Copy data back from temp table
                cursor.execute(f"INSERT INTO email_account ({columns_str}) SELECT {columns_str} FROM email_account_temp")
                
                # Drop temp table
                cursor.execute("DROP TABLE email_account_temp")
                
                # Commit transaction
                cursor.execute("COMMIT")
                logger.info("Successfully recreated table with imap_verified_at column")
                
            except Exception as ex:
                cursor.execute("ROLLBACK")
                logger.error(f"Table recreation failed: {str(ex)}")
                return False
            
        # Verify the column was added successfully
        cursor.execute("PRAGMA table_info(email_account)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"Updated email_account columns: {column_names}")
        
        # Final verification
        if 'imap_verified_at' in column_names:
            logger.info("MIGRATION SUCCESSFUL - imap_verified_at column now exists!")
            conn.close()
            return True
        else:
            logger.error("MIGRATION FAILED - imap_verified_at column is still missing!")
            conn.close()
            return False
            
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    # Get the database path from environment variable or use default
    default_db_path = "email_automation.db"
    db_path = os.environ.get("DATABASE_PATH", default_db_path)
    
    # If path is relative, make it absolute
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        
    logger.info(f"Using database at: {db_path}")
    
    # Run the migration
    success = migrate_imap_verified_column(db_path)
    
    if success:
        logger.info("IMAP migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("IMAP migration failed!")
        sys.exit(1) 