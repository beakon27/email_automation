"""
Package initialization for the app module.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import pytz
from flask_socketio import SocketIO

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-testing')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///email_automation.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize database
db = SQLAlchemy(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize background scheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone(os.environ.get('TIMEZONE', 'UTC')))
scheduler.start()

# Get timezone from environment
app.config['TIMEZONE'] = os.environ.get('TIMEZONE', 'UTC')
try:
    app.timezone = pytz.timezone(app.config['TIMEZONE'])
except:
    app.timezone = pytz.UTC

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/beakon.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Beakon Solutions system startup')

# Import models to ensure they are registered with SQLAlchemy
from app.models import models

# Create all database tables
with app.app_context():
    try:
        # Force SQLAlchemy to create all tables
        db.create_all()
        
        # Ensure Campaign table exists
        if not db.engine.dialect.has_table(db.engine, 'campaign'):
            models.Campaign.__table__.create(db.engine)
            app.logger.info("Campaign table created")
            
        # Ensure email table has campaign_id column
        inspector = db.inspect(db.engine)
        email_columns = [col['name'] for col in inspector.get_columns('email')]
        if 'campaign_id' not in email_columns:
            with db.engine.connect() as conn:
                conn.execute(db.text("""
                    ALTER TABLE email 
                    ADD COLUMN campaign_id INTEGER 
                    REFERENCES campaign(id)
                """))
                app.logger.info("campaign_id column added to email table")
                
        app.logger.info("Database tables verified and updated")
        
    except Exception as e:
        app.logger.error(f"Error updating database schema: {str(e)}")
        
# Force SQLAlchemy to reflect tables from the database
with app.app_context():
    try:
        app.logger.info("Refreshing SQLAlchemy metadata")
        db.Model.metadata.reflect(db.engine)
        app.logger.info("SQLAlchemy metadata refreshed")
    except Exception as e:
        app.logger.error(f"Error refreshing SQLAlchemy metadata: {str(e)}")

# Initialize socketio for real-time updates
app.logger.info("Initializing SocketIO for real-time updates")

# Add middleware to check database schema on every request - DISABLED by user request
# @app.before_request
# def check_db_schema():
#     # Only perform the check for HTML page requests, not static files, etc.
#     if not request.path.startswith('/static/') and request.endpoint:
#         # Skip the migration check if we're already going to the migration page
#         if request.endpoint == 'migrate_imap':
#             return
#             
#         # Skip if we're accessing static resources or other non-model endpoints
#         try:
#             # Check if schema is up to date
#             if not check_database_schema():
#                 flash('Database schema needs to be updated for IMAP support. Please click "Update Database" below.', 'warning')
#                 return redirect(url_for('migrate_imap'))
#         except Exception as e:
#             # If checking fails, don't block access to the app
#             app.logger.error(f"Error checking database schema: {str(e)}")
#             return

# Database verification is now unified and handled by verify_database_on_request
# We've removed the redundant auto_fix_database_schema function to simplify the code 
# and prevent circular imports and race conditions during verification.

# Note: Routes are imported elsewhere to avoid circular imports 

# Database verification is now run in app.py to avoid circular imports 