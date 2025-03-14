"""
Migration script to add campaign_id column to email table
"""

import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    # Import db from app
    from app import db
    from app.models.models import Email, Campaign
    
    logger.info("Starting email table migration")
    
    # Use SQLAlchemy engine directly for schema changes
    with db.engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(email)"))
        columns = result.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'campaign_id' not in column_names:
            logger.info("Adding campaign_id column to email table")
            conn.execute(text("ALTER TABLE email ADD COLUMN campaign_id INTEGER REFERENCES campaign(id)"))
            logger.info("Successfully added campaign_id column")
        else:
            logger.info("campaign_id column already exists")
        
        # Update emails with template_id to associate with campaigns
        try:
            logger.info("Associating emails with campaigns based on template_id")
            result = conn.execute(text("""
                UPDATE email
                SET campaign_id = (
                    SELECT c.id FROM campaign c
                    WHERE c.template_id = email.template_id
                    ORDER BY ABS(strftime('%s', c.created_at) - strftime('%s', email.created_at))
                    LIMIT 1
                )
                WHERE campaign_id IS NULL AND template_id IS NOT NULL
            """))
            logger.info("Successfully associated emails with campaigns")
        except Exception as e:
            logger.error(f"Error associating emails with campaigns: {str(e)}")
    
    logger.info("Migration complete")

if __name__ == "__main__":
    run_migration() 