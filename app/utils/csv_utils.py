"""
CSV import utilities for the Beakon Solutions platform.
"""

import pandas as pd
import logging
from app import db
from app.models.models import Recipient, ImportLog
from app.utils.email_utils import validate_email, extract_first_name

logger = logging.getLogger(__name__)

def import_csv(file_path, has_header=True):
    """
    Import a CSV file with email addresses
    
    Args:
        file_path (str): Path to the CSV file
        has_header (bool): Whether the CSV has a header row
        
    Returns:
        tuple: (success, import_log_id)
    """
    try:
        # Create import log
        import_log = ImportLog(filename=file_path.split('/')[-1])
        db.session.add(import_log)
        db.session.commit()
        
        # Read CSV file
        if has_header:
            df = pd.read_csv(file_path)
        else:
            df = pd.read_csv(file_path, header=None, names=['email', 'first_name'])
        
        total_records = len(df)
        valid_records = 0
        duplicate_records = 0
        invalid_records = 0
        
        # Check if CSV has the required columns
        if 'email' not in df.columns:
            # Try to find an email column by checking column types and values
            for col in df.columns:
                if df[col].dtype == 'object' and df[col].str.contains('@').any():
                    df = df.rename(columns={col: 'email'})
                    break
            else:
                logger.error(f"No email column found in CSV: {file_path}")
                import_log.total_records = total_records
                import_log.invalid_records = total_records
                db.session.commit()
                return False, import_log.id
        
        # Process each row
        for _, row in df.iterrows():
            email = row['email'].strip().lower() if isinstance(row['email'], str) else str(row['email']).strip().lower()
            
            # Validate email
            if not validate_email(email):
                invalid_records += 1
                continue
                
            # Check for first name column
            first_name = None
            if 'first_name' in df.columns and pd.notna(row['first_name']):
                first_name = row['first_name'].strip().capitalize() if isinstance(row['first_name'], str) else None
                
            # Check if recipient already exists - automatically skip duplicates without asking
            existing = Recipient.query.filter_by(email=email).first()
            if existing:
                duplicate_records += 1
                logger.info(f"Skipping duplicate email: {email}")
                continue
                
            # If no first_name provided, extract it from the email
            if not first_name:
                first_name = extract_first_name(email)
                
            # Create new recipient
            recipient = Recipient(email=email, first_name=first_name)
            db.session.add(recipient)
            valid_records += 1
            
        # Commit changes
        db.session.commit()
        
        # Update import log
        import_log.total_records = total_records
        import_log.valid_records = valid_records
        import_log.duplicate_records = duplicate_records
        import_log.invalid_records = invalid_records
        db.session.commit()
        
        logger.info(f"CSV import completed: {valid_records} valid, {duplicate_records} duplicate, {invalid_records} invalid records")
        return True, import_log.id
        
    except Exception as e:
        logger.error(f"Error importing CSV {file_path}: {str(e)}")
        db.session.rollback()
        
        # Update import log if created
        if 'import_log' in locals() and import_log and import_log.id:
            import_log.invalid_records = total_records if 'total_records' in locals() else 0
            db.session.commit()
            
        return False, import_log.id if 'import_log' in locals() and import_log and import_log.id else None 