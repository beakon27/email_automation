"""
Main serverless entry point for the Beakon Solutions system on Vercel.
"""

import os
import sys
import logging
from flask import Flask, redirect, url_for

# Adjust the path to include the email_automation directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging through Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the app after path adjustment
try:
    from app import app, db
    from app.controllers import routes
    logger.info("Successfully imported app modules")
except Exception as e:
    logger.error(f"Error importing app modules: {str(e)}")
    raise

# Replace SQLite with Postgres for production
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    logger.info(f"Using database URL: {os.environ.get('DATABASE_URL')}")

# Disable background threads as they're not supported on Vercel
app.config['USE_BACKGROUND_THREADS'] = False

# Configure S3 storage for file uploads
app.config['USE_S3_STORAGE'] = os.environ.get('USE_S3_STORAGE', 'True').lower() == 'true'
app.config['S3_BUCKET'] = os.environ.get('S3_BUCKET', 'beakon-solutions')
app.config['AWS_ACCESS_KEY'] = os.environ.get('AWS_ACCESS_KEY', '')
app.config['AWS_SECRET_KEY'] = os.environ.get('AWS_SECRET_KEY', '')

# Create all database tables if they don't exist
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created or verified")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

# Define the index route
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

# WSGI handler
def handler(event, context):
    return app(event, context)

# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port) 