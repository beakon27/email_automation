#!/usr/bin/env python3
"""
Database Migration Script

This script provides a comprehensive solution to fix database schema issues:
1. Creates a backup of the existing database
2. Extracts existing data from the database
3. Creates a new database with the correct schema including the missing columns
4. Migrates the data from the old schema to the new schema
"""

import os
import sys
import sqlite3
import shutil
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def backup_database(db_path):
    """Creates a backup of the database file"""
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at: {db_path}")
        return False
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.{timestamp}.bak"
    
    try:
        # Copy the database file
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created database backup at: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create database backup: {str(e)}")
        return False

def get_table_creation_sql(source_db_path, table_name):
    """Gets the SQL to recreate a table with the required schema"""
    conn = sqlite3.connect(source_db_path)
    cursor = conn.cursor()
    
    # Get the CREATE TABLE statement
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    create_sql = cursor.fetchone()[0]
    
    conn.close()
    return create_sql

def modify_table_schema(create_sql, columns_to_add):
    """Modifies a CREATE TABLE statement to include additional columns"""
    # Find the position before the closing parenthesis
    closing_paren_pos = create_sql.rstrip().rfind(')')
    if closing_paren_pos == -1:
        logger.error(f"Invalid CREATE TABLE statement: {create_sql}")
        return None
    
    # Add the new columns before the closing parenthesis
    prefix = create_sql[:closing_paren_pos].rstrip()
    suffix = create_sql[closing_paren_pos:]
    
    # Add a comma if there are existing columns
    if not prefix.endswith('('):
        prefix += ','
    
    # Add the new column definitions
    column_defs = ' '.join([f"{name} {dtype}," for name, dtype in columns_to_add[:-1]])
    column_defs += f" {columns_to_add[-1][0]} {columns_to_add[-1][1]}"
    
    # Combine the parts
    new_create_sql = f"{prefix} {column_defs}{suffix}"
    
    return new_create_sql

def extract_table_data(source_db_path, table_name):
    """Extracts all data from a table in the source database"""
    conn = sqlite3.connect(source_db_path)
    conn.row_factory = sqlite3.Row  # This makes rows accessible by column name
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Get all rows
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    conn.close()
    
    return columns, rows

def migrate_database(source_db_path, destination_db_path):
    """
    Creates a new database with the correct schema and migrates data
    """
    # First, get all tables from the source database
    source_conn = sqlite3.connect(source_db_path)
    source_cursor = source_conn.cursor()
    
    # Get list of all tables
    source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [table[0] for table in source_cursor.fetchall()]
    logger.info(f"Found tables: {tables}")
    
    # Create new database
    if os.path.exists(destination_db_path):
        os.remove(destination_db_path)
    
    dest_conn = sqlite3.connect(destination_db_path)
    dest_cursor = dest_conn.cursor()
    
    # Process each table
    for table in tables:
        # Skip SQLite internal tables
        if table.startswith('sqlite_'):
            continue
        
        # Extract table data
        columns, rows = extract_table_data(source_db_path, table)
        logger.info(f"Extracted {len(rows)} rows from {table}")
        
        # Get table creation SQL
        create_sql = get_table_creation_sql(source_db_path, table)
        
        # Add missing columns to table schema
        missing_columns = []
        if table == 'email_account' and 'imap_verified_at' not in columns:
            missing_columns.append(('imap_verified_at', 'TIMESTAMP'))
        
        # Create table in destination database
        if missing_columns:
            logger.info(f"Adding columns {missing_columns} to {table}")
            create_sql = modify_table_schema(create_sql, missing_columns)
        
        dest_cursor.execute(create_sql)
        logger.info(f"Created table {table} in destination database")
        
        # Prepare for data insertion
        if rows:
            # Prepare column names for INSERT statement
            # Only include columns that existed in old schema
            insert_cols = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])
            
            # Insert data
            for row in rows:
                row_data = [row[col] for col in columns]
                dest_cursor.execute(f"INSERT INTO {table} ({insert_cols}) VALUES ({placeholders})", row_data)
            
            logger.info(f"Inserted {len(rows)} rows into {table}")
    
    # Commit changes and close connections
    dest_conn.commit()
    source_conn.close()
    dest_conn.close()
    
    return True

def fix_database_schema(db_path):
    """Main function to fix database schema issues"""
    logger.info(f"Starting database schema migration for: {db_path}")
    
    # Backup the original database
    if not backup_database(db_path):
        logger.error("Aborting migration due to backup failure")
        return False
    
    # Create a temporary path for the new database
    temp_db_path = f"{db_path}.new"
    
    try:
        # Migrate database
        if not migrate_database(db_path, temp_db_path):
            logger.error("Database migration failed")
            return False
        
        # Replace old database with new one
        # First, close all connections to database
        logger.info("Replacing old database with migrated version...")
        
        # Replace the database
        os.replace(temp_db_path, db_path)
        logger.info("Database replacement successful")
        
        return True
    except Exception as e:
        logger.error(f"Error during database migration: {str(e)}")
        return False

if __name__ == "__main__":
    # Default database path
    default_db_path = "email_automation.db"
    
    # Allow custom path from command line
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db_path
    
    # Make path absolute if it's relative
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
    
    # Run the migration
    if fix_database_schema(db_path):
        logger.info("Database migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Database migration failed")
        sys.exit(1) 